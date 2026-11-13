"""End-to-end command execution: NLP → Vision → Automation → Audit."""

from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional

from src.automation.engine import AutomationEngine
from src.automation.safety import SafetyLimitError, SafetyPolicy
from src.db.database import Database
from src.db.repositories import NLPCommandRepository, UserConfRepository
from src.logging_audit.service import AuditService
from src.nlp.engine import NLPEngine, ParsedCommand
from src.nlp.planner import ActionPlan, CommandPlanner, PlanStep
from src.agent.browser import apply_browser
from src.agent.logs import agent_log
from src.agent.resolver import resolve_click_target, visible_loginish
from src.agent.semantic import expand_click_query
from src.agent.sensitive import history_line_for_type, is_sensitive_request
from src.agent.verify import click_succeeded, page_snapshot
from src.vision.engine import VisionEngine
from src.vision.search_result import (
    FIRST_RESULT_ELEMENT,
    is_first_result_phrase,
    parse_result_index,
)
from src.workflows.service import WorkflowService


class AutomationPipeline:
    def __init__(
        self,
        config: Dict[str, Any],
        db: Database,
        *,
        nlp: Optional[NLPEngine] = None,
        vision: Optional[VisionEngine] = None,
        automation: Optional[AutomationEngine] = None,
        workflows: Optional[WorkflowService] = None,
        audit: Optional[AuditService] = None,
    ) -> None:
        self.config = config
        self.db = db
        nlp_cfg = config.get("nlp", {})
        self.nlp = nlp or NLPEngine(
            nlp_cfg.get("spacy_model", "en_core_web_sm"),
            min_confidence=float(nlp_cfg.get("min_confidence", 0.45)),
        )
        self.vision = vision or VisionEngine(config)
        self.automation = automation or AutomationEngine(config)
        self.workflows = workflows or WorkflowService(db)
        self.audit = audit or AuditService(db)
        self.nlp_repo = NLPCommandRepository(db)
        self.conf_repo = UserConfRepository(db)
        self.planner = CommandPlanner(
            mode=str((config.get("nlp") or {}).get("mode", "local")),
            min_confidence=float(nlp_cfg.get("min_confidence", 0.45)),
        )
        self.safety = SafetyPolicy.from_config(config)
        self._stop_requested = False
        self._stop_reason = ""
        self.last_frame = None
        self.last_boxes: List[Dict[str, Any]] = []
        self.last_plan: Optional[Dict[str, Any]] = None
        self.last_capture_path = ""

    def request_stop(self, reason: str = "User requested emergency stop.") -> None:
        self._stop_requested = True
        self._stop_reason = reason

    def apply_user_settings(self, user_id: int) -> None:
        conf = self.conf_repo.get_map(user_id)
        if not conf:
            return
        self.automation.set_dry_run(str(conf.get("dry_run", "0")) in ("1", "true", "True"))
        self.automation.failsafe = str(conf.get("failsafe", "1")) in ("1", "true", "True")
        self.automation.pause_seconds = float(conf.get("pause_seconds", 0.04))
        if self.automation._pyautogui is not None:
            self.automation._pyautogui.PAUSE = self.automation.pause_seconds
            self.automation._pyautogui.FAILSAFE = self.automation.failsafe
        mode = str(conf.get("ai_mode") or self.config.get("nlp", {}).get("mode") or "local")
        self.planner.mode = "enhanced" if mode in ("enhanced", "cloud", "ai") else "local"
        self.planner.min_confidence = float(
            conf.get("min_confidence", self.config.get("nlp", {}).get("min_confidence", 0.45))
        )
        self.safety = SafetyPolicy.from_config(self.config, conf)

    def preview_plan(self, text: str, *, source: str = "text") -> ActionPlan:
        parsed = self.nlp.parse(text)
        if parsed.intent == "unknown" and source == "voice" and (parsed.raw_text or text).strip():
            spoken = (parsed.raw_text or text).strip()
            parsed.intent = "type_text"
            parsed.entities = {**(parsed.entities or {}), "text": spoken}
            parsed.confidence = max(parsed.confidence, 0.4)
            parsed.steps = [
                {
                    "intent": "type_text",
                    "entities": dict(parsed.entities),
                    "confidence": parsed.confidence,
                }
            ]
        return self.planner.plan(parsed, parsed.raw_text or text)

    def _ensure_live_automation(self, intents: Optional[List[str]] = None) -> None:
        """Require PyAutoGUI only for mouse/keyboard steps (not browser URL launches)."""
        if self.automation.dry_run:
            return
        needs_mouse = {
            "click_text",
            "click_button",
            "fill_form",
            "type_text",
            "press_key",
            "scroll",
            "wait",
        }
        required = any(i in needs_mouse for i in (intents or []))
        if not required:
            return
        if not self.automation.mouse_ready:
            detail = getattr(self.automation, "_pyautogui_error", "") or "import failed"
            raise RuntimeError(
                "PyAutoGUI is unavailable for mouse/keyboard actions "
                f"({detail}). On Linux install: sudo apt-get install -y python3-tk. "
                "Or enable dry-run in Settings."
            )

    def run_text_command(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        source: str = "text",
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        self._stop_requested = False
        self._stop_reason = ""
        self._status_cb = status_cb or (lambda _m: None)
        started = time.perf_counter()
        emit = self._status_cb

        emit("AI planner: understanding your goal…")
        parsed = self.nlp.parse(text)
        # Voice: always turn STT into an action (type if we don't recognize a verb)
        if parsed.intent == "unknown" and source == "voice" and (parsed.raw_text or text).strip():
            spoken = (parsed.raw_text or text).strip()
            parsed.intent = "type_text"
            parsed.entities = {**(parsed.entities or {}), "text": spoken}
            parsed.confidence = max(parsed.confidence, 0.4)
            parsed.steps = [
                {
                    "intent": "type_text",
                    "entities": dict(parsed.entities),
                    "confidence": parsed.confidence,
                }
            ]

        plan = self.planner.plan(parsed, parsed.raw_text or text)
        self.last_plan = plan.to_dict()
        emit(
            f"Plan ready · {plan.summary} · confidence {int(plan.confidence * 100)}% · "
            f"~{plan.estimated_s:.0f}s"
        )

        command_id = self.nlp_repo.create(
            raw_text=text,
            parsed_intent=parsed.intent,
            entities={**(parsed.entities or {}), "plan": [s.title for s in plan.steps]},
            confidence=parsed.confidence,
            source=source,
            user_id=user_id,
        )

        if plan.needs_clarification and parsed.intent == "unknown":
            duration = int((time.perf_counter() - started) * 1000)
            hints = " · ".join(plan.suggestions[:4]) or "Open Chrome · Click Login"
            msg = (
                "I couldn't fully understand that.\n"
                f"You said: “{text}”\n"
                f"Maybe you meant: {hints}"
            )
            log_id = self.audit.log_execution(
                status="Failed",
                duration_ms=duration,
                error_message=msg,
                details={"parsed": parsed.to_dict(), "plan": plan.to_dict()},
                user_id=user_id,
                command_id=command_id,
            )
            emit(msg)
            return {
                "ok": False,
                "parsed": parsed.to_dict(),
                "plan": plan.to_dict(),
                "suggestions": plan.suggestions,
                "command_id": command_id,
                "log_id": log_id,
                "error": msg,
            }

        # Special: run named workflow
        if parsed.intent == "run_workflow" and user_id is not None:
            return self.run_workflow_by_name(
                user_id,
                parsed.entities.get("workflow", ""),
                command_id=command_id,
                status_cb=status_cb,
            )

        actions_done: List[Dict[str, Any]] = []
        captures: List[str] = []
        error: Optional[str] = None
        completed = 0

        try:
            self._ensure_live_automation(plan.executable_intents())
            before = None
            action_count = 0
            for step in plan.steps:
                elapsed = time.perf_counter() - started
                self.safety.check_time(elapsed)
                if self._stop_requested:
                    error = self._stop_reason or "Stopped by user"
                    break
                emit(f"● {step.title}")
                step.status = "running"
                if step.kind == "inspect":
                    result = self._inspect_screen(str((step.entities or {}).get("element") or ""))
                    actions_done.append(result)
                    if result.get("capture_path"):
                        captures.append(result["capture_path"])
                    if result.get("boxes") is not None:
                        self.last_boxes = result.get("boxes") or []
                    step.status = "done"
                    emit(f"✓ {step.title}")
                    continue
                if step.kind == "verify":
                    after = self.vision.capture_screen()
                    check = self.vision.frame_changed(before, after)
                    result = {"intent": "verify_screen", "verification": check}
                    actions_done.append(result)
                    if self.safety.verify_change and not check.get("changed") and not self.automation.dry_run:
                        emit("⚠ Screen did not change — retrying last action is up to the next step")
                    step.status = "done" if check.get("changed") or self.automation.dry_run else "done"
                    emit(f"✓ {step.title}" if check.get("changed") or self.automation.dry_run else f"⚠ {step.title}")
                    before = after
                    continue

                action_count += 1
                self.safety.check_actions(action_count)
                before = self.vision.last_frame if step.intent in ("click_text", "click_button") else before
                result = self._execute_step_with_retry(
                    {"intent": step.intent, "entities": step.entities},
                    user_id=user_id,
                )
                actions_done.append(result)
                if result.get("needs_confirm") or result.get("needs_secret"):
                    emit(result.get("confirm_prompt") or "Need a confirmation before I continue.")
                    return {
                        "ok": False,
                        "needs_confirm": bool(result.get("needs_confirm")),
                        "needs_secret": bool(result.get("needs_secret")),
                        "confirm_prompt": result.get("confirm_prompt") or "",
                        "candidates": result.get("candidates") or [],
                        "parsed": parsed.to_dict(),
                        "plan": plan.to_dict(),
                        "actions": actions_done,
                        "command_id": command_id,
                        "error": result.get("confirm_prompt") or "Need confirmation",
                        "boxes": result.get("boxes") or self.last_boxes,
                    }
                completed += 1
                if result.get("capture_path"):
                    captures.append(result["capture_path"])
                    self.last_capture_path = result["capture_path"]
                if result.get("boxes") is not None:
                    self.last_boxes = result.get("boxes") or []
                if self.vision.last_frame is not None:
                    self.last_frame = self.vision.last_frame
                step.status = "done"
                emit(f"✓ {step.title}")
        except SafetyLimitError as exc:
            error = str(exc)
        except Exception as exc:
            error = str(exc)

        duration = int((time.perf_counter() - started) * 1000)
        status = "Failed" if error else "Success"
        if error and ("Stopped" in error or "emergency" in error.lower()):
            status = "Exception"
        remaining = max(0, len(plan.steps) - completed)
        log_id = self.audit.log_execution(
            status=status,
            duration_ms=duration,
            error_message=error or "",
            details={
                "parsed": parsed.to_dict(),
                "plan": plan.to_dict(),
                "actions": actions_done,
                "completed": completed,
                "remaining": remaining,
            },
            user_id=user_id,
            command_id=command_id,
            capture_paths=captures,
        )
        if error:
            emit(f"Error: {error}")
        else:
            emit("✓ Completed successfully")
        return {
            "ok": error is None,
            "parsed": parsed.to_dict(),
            "plan": plan.to_dict(),
            "actions": actions_done,
            "command_id": command_id,
            "log_id": log_id,
            "error": error,
            "boxes": self.last_boxes,
            "dry_run": self.automation.dry_run,
            "completed": completed,
            "remaining": remaining,
            "suggestions": plan.suggestions,
        }

    def run_workflow(
        self,
        workflow_id: int,
        *,
        user_id: Optional[int] = None,
        command_id: Optional[int] = None,
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        self._stop_requested = False
        emit = status_cb or (lambda _m: None)
        started = time.perf_counter()
        wf = self.workflows.get_workflow(workflow_id)
        if not wf:
            log_id = self.audit.log_execution(
                status="Failed",
                duration_ms=0,
                error_message="Workflow not found",
                user_id=user_id,
                command_id=command_id,
                workflow_id=workflow_id,
            )
            return {"ok": False, "error": "Workflow not found", "log_id": log_id}
        if user_id is not None and int(wf.get("user_id") or 0) != int(user_id):
            return {"ok": False, "error": "Workflow not found for this user"}

        actions_done: List[Dict[str, Any]] = []
        captures: List[str] = []
        error: Optional[str] = None
        try:
            tasks = WorkflowService.fill_empty_clicks_after_search(list(wf.get("tasks") or []))
            self._ensure_live_automation(
                [str((WorkflowService.task_to_step(t) or {}).get("intent") or "") for t in tasks]
            )
            for task in tasks:
                if self._stop_requested:
                    error = "Stopped by user"
                    break
                step = WorkflowService.task_to_step(task)
                emit(f"Workflow step: {step['intent']}")
                result = self._execute_step(step, user_id=user_id)
                actions_done.append(result)
                if result.get("capture_path"):
                    captures.append(result["capture_path"])
        except Exception as exc:
            error = str(exc)

        duration = int((time.perf_counter() - started) * 1000)
        status = "Failed" if error else "Success"
        if error and "Stopped" in error:
            status = "Exception"
        log_id = self.audit.log_execution(
            status=status,
            duration_ms=duration,
            error_message=error or "",
            details={"workflow_id": workflow_id, "actions": actions_done},
            user_id=user_id,
            workflow_id=workflow_id,
            command_id=command_id,
            capture_paths=captures,
        )
        return {
            "ok": error is None,
            "actions": actions_done,
            "log_id": log_id,
            "error": error,
            "dry_run": self.automation.dry_run,
            "workflow": wf,
        }

    def run_workflow_by_name(
        self,
        user_id: int,
        name: str,
        *,
        command_id: Optional[int] = None,
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        emit = status_cb or (lambda _m: None)
        wf = self.workflows.find_by_name(user_id, name)
        if not wf:
            names = [w.get("name", "") for w in self.workflows.list_workflows(user_id)]
            hint = (", ".join(names[:6]) if names else "create one on the Workflows page")
            started_error = (
                f"Workflow not found: “{name}”. "
                f"Say the workflow name after run. Available: {hint}"
            )
            emit(started_error)
            log_id = self.audit.log_execution(
                status="Failed",
                duration_ms=0,
                error_message=started_error,
                user_id=user_id,
                command_id=command_id,
            )
            return {"ok": False, "error": started_error, "log_id": log_id}
        emit(f"Running workflow “{wf.get('name')}”…")
        return self.run_workflow(
            wf["workflow_id"],
            user_id=user_id,
            command_id=command_id,
            status_cb=status_cb,
        )

    def _inspect_screen(self, element: str = "") -> Dict[str, Any]:
        emit = getattr(self, "_status_cb", None) or (lambda _m: None)
        emit("Reading the screen (OCR)…")
        frame = self.vision.capture_screen()
        preview = self.vision.ocr_preview(frame)
        boxes = list(preview.boxes or [])
        hit = None
        if element.strip():
            hit = self.vision.locate(element, frame=frame)
            if hit.found:
                boxes = hit.boxes or boxes
        path = self.vision.save_capture(frame, label="inspect", boxes=boxes)
        self.last_frame = frame
        self.last_boxes = boxes
        self.last_capture_path = path
        return {
            "intent": "inspect_screen",
            "capture_path": path,
            "boxes": boxes,
            "detection": None
            if hit is None
            else {
                "found": hit.found,
                "label": hit.label,
                "confidence": hit.confidence,
                "method": hit.method,
                "x": hit.x,
                "y": hit.y,
            },
        }

    def _execute_step_with_retry(
        self, step: Dict[str, Any], *, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        attempts = max(1, int(self.safety.max_retries))
        for attempt in range(1, attempts + 1):
            if self._stop_requested:
                raise RuntimeError(self._stop_reason or "Stopped by user")
            try:
                return self._execute_step(step, user_id=user_id)
            except Exception as exc:
                last_exc = exc
                emit = getattr(self, "_status_cb", None) or (lambda _m: None)
                if attempt >= attempts:
                    break
                emit(f"Not found / failed — retry {attempt}/{attempts - 1} after {self.safety.retry_delay:.1f}s")
                self.automation.wait(self.safety.retry_delay)
                self.vision.capture_screen()
        assert last_exc is not None
        raise last_exc

    def _click_ranked_result(self, index: int, frame, result: Dict[str, Any]) -> Dict[str, Any]:
        emit = getattr(self, "_status_cb", None) or (lambda _m: None)
        index = max(1, int(index or 1))
        detection = self.vision.find_ranked_search_result(index, frame)
        if not detection.found:
            emit(f"Reading the page again for result {index}…")
            time.sleep(0.35)
            frame = self.vision.capture_screen()
            self.automation.capture_region = dict(self.vision.last_region)
            detection = self.vision.find_ranked_search_result(index, frame)
        boxes = [b for b in (detection.boxes or []) if b.get("index")]
        if not detection.found and boxes:
            hit = next((b for b in boxes if int(b.get("index") or 0) == index), None)
            if hit is None and boxes:
                hit = boxes[min(index, len(boxes)) - 1]
            detection.found = True
            detection.x = int(hit["x"] + int(hit.get("w") or hit.get("width") or 8) // 2)
            detection.y = int(hit["y"] + int(hit.get("h") or hit.get("height") or 8) // 2)
            detection.width = int(hit.get("w") or hit.get("width") or 8)
            detection.height = int(hit.get("h") or hit.get("height") or 8)
            detection.label = str(hit.get("label") or f"result {index}")
            detection.confidence = 0.82
        result["detection"] = {
            "found": detection.found,
            "x": detection.x,
            "y": detection.y,
            "width": detection.width,
            "height": detection.height,
            "method": detection.method,
            "confidence": detection.confidence,
            "label": detection.label,
        }
        result["boxes"] = boxes
        if not detection.found:
            raise RuntimeError(
                f"I cannot see result {index} on the current Chrome page. "
                "Make sure Google results are visible, then say "
                "click the first link or click the second result."
            )
        emit(
            f"◆highlight {detection.x - detection.width // 2} "
            f"{detection.y - detection.height // 2} {detection.width} {detection.height}"
        )
        emit(f"Clicking result {index}: {detection.label}…")
        agent_log(f"Candidate: {detection.label}")
        agent_log(f"Confidence: {detection.confidence:.2f}")
        clicked = self.automation.click(
            detection.x, detection.y, label=detection.label or f"result {index}"
        )
        time.sleep(0.4)
        after = self.vision.capture_screen()
        check = self.vision.frame_changed(frame, after, threshold=0.01)
        result["automation"] = clicked
        result["verification"] = check
        result["capture_path"] = self.vision.save_capture(
            frame, label=f"result_{index}", boxes=boxes[-8:]
        )
        if not check.get("changed") and not self.automation.dry_run:
            result["needs_retry"] = True
            result["error"] = (
                f"Result {index} ({detection.label}) didn't appear to open. Should I try again?"
            )
        return result

    def _history_has_recent_search(self) -> bool:
        for item in reversed(self.automation.history[-16:]):
            action = item.get("action")
            if action in ("search_google", "address_bar_search"):
                return True
            if action in ("wait", "move_to", "open_app", "open_url"):
                continue
            return False
        return False

    def _click_element(self, element: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {"intent": "click_button", "entities": entities}
        element = (element or "").strip()
        result_index = int(entities.get("result_index") or 0) or parse_result_index(element or "")
        first = bool(entities.get("first_result")) or is_first_result_phrase(element) or result_index == 1
        if not element and not first and not result_index:
            if self._history_has_recent_search():
                first = True
                result_index = 1
                element = FIRST_RESULT_ELEMENT
            elif entities.get("x") is not None and entities.get("y") is not None:
                x, y = int(entities["x"]), int(entities["y"])
                result["automation"] = self.automation.click(x, y, label=str(entities.get("label") or ""))
                return result
            else:
                raise RuntimeError(
                    "Click has no target. Say the button or link name, for example “click login”."
                )
        if entities.get("x") is not None and entities.get("y") is not None and not first and not result_index:
            x, y = int(entities["x"]), int(entities["y"])
            result["automation"] = self.automation.click(
                x, y, label=element or str(entities.get("label") or "")
            )
            return result
        emit = getattr(self, "_status_cb", None) or (lambda _m: None)
        if result_index:
            emit(f"Looking at the current screen for result {result_index}…")
        elif first:
            result_index = 1
            element = FIRST_RESULT_ELEMENT
            emit("Looking at the current screen for the first search result…")
        else:
            emit(f"Looking for “{element}” on screen…")
        time.sleep(0.55)
        frame = self.vision.capture_screen()
        self.automation.capture_region = dict(self.vision.last_region)
        if not self.vision.last_capture_ok:
            raise RuntimeError(
                f"Screen capture failed: {self.vision.last_capture_error or 'unknown error'}"
            )
        if result_index:
            return self._click_ranked_result(result_index, frame, result)
        prefer = "template" if entities.get("prefer") == "template" else "ocr"
        if entities.get("skip_match"):
            return self._click_via_locate(element, prefer, frame, result, emit)
        return self._click_via_resolver(element, frame, result, emit)

    def _click_via_resolver(self, element: str, frame, result: Dict[str, Any], emit) -> Dict[str, Any]:
        query = expand_click_query(element) or str(element or "")
        result["query"] = element
        result["expanded"] = query
        emit("Analyzing screen (accessibility → OCR → vision)…")
        agent_log("Hybrid resolver started")
        exclude: set = set()
        last_visible: List[Dict[str, Any]] = []
        capture_path = ""
        for attempt in range(1, 4):
            if attempt > 1:
                emit("Recovering — trying the next strategy…")
                agent_log(f"Recovery round {attempt}")
                time.sleep(0.55)
                frame = self.vision.capture_screen()
                self.automation.capture_region = dict(self.vision.last_region)
            before_sig = page_snapshot()
            result["page_before"] = before_sig
            resolved = resolve_click_target(query, self.vision, frame, exclude_ids=exclude)
            result["strategies"] = list(resolved.strategies)
            result["matches"] = [
                {
                    "text": m.element.text,
                    "score": m.score,
                    "type": m.element.type,
                    "source": m.element.source,
                }
                for m in resolved.matches[:4]
            ]
            if resolved.state is not None:
                capture_path = resolved.state.capture_path or capture_path
                result["screen"] = {
                    "count": len(resolved.state.elements),
                    "path": resolved.state.capture_path,
                }
                last_visible = visible_loginish(resolved.state.elements)
            if resolved.element:
                agent_log(f"Candidate: {resolved.element.text}")
                agent_log(f"Confidence: {resolved.score:.2f} ({resolved.method})")
            if resolved.ambiguous and resolved.candidates:
                result["needs_confirm"] = True
                result["confirm_prompt"] = resolved.message or (
                    f"I found “{resolved.element.text}”. Do you mean this?"
                    if resolved.element
                    else "I found more than one matching control."
                )
                result["candidates"] = [
                    {
                        "text": m.element.text,
                        "score": m.score,
                        "x": m.element.x,
                        "y": m.element.y,
                        "width": m.element.width,
                        "height": m.element.height,
                    }
                    for m in resolved.matches[:3]
                ] or [
                    {
                        "text": el.text,
                        "score": 0.8,
                        "x": el.x,
                        "y": el.y,
                        "width": el.width,
                        "height": el.height,
                    }
                    for el in resolved.candidates[:3]
                ]
                result["capture_path"] = capture_path
                return result
            candidates = []
            seen: set = set()
            for el in ([resolved.element] if resolved.element else []) + list(resolved.candidates):
                if el is None or el.id in exclude or el.id in seen:
                    continue
                seen.add(el.id)
                candidates.append(el)
            if not candidates:
                continue
            if resolved.weak and attempt < 3:
                emit("Low-confidence match — checking other strategies first…")
                continue
            el = candidates[0]
            clicked, check, after_sig, ok = self._click_resolved(
                el, frame, before_sig, emit
            )
            result["detection"] = {
                "found": True,
                "x": el.center[0],
                "y": el.center[1],
                "width": el.width,
                "height": el.height,
                "method": el.source or resolved.method,
                "confidence": resolved.score or el.confidence,
                "label": el.text,
            }
            result["automation"] = clicked
            result["verification"] = check
            result["page_after"] = after_sig
            result["boxes"] = [el.to_dict()]
            result["capture_path"] = capture_path
            if self.automation.dry_run or ok:
                return result
            emit(f"“{el.text}” didn't change the page — recovering…")
            agent_log(f"No PAGE_CHANGED after {resolved.method} click")
            exclude.add(el.id)
        result["capture_path"] = capture_path
        if last_visible:
            result["needs_confirm"] = True
            result["confirm_prompt"] = (
                f"I couldn't lock onto “{element}” after accessibility, OCR, and vision. "
                "Do you mean one of these?"
            )
            result["candidates"] = last_visible
            return result
        if not (element or "").strip():
            raise RuntimeError(
                "Click has no target. Say the button or link name, for example “click login”."
            )
        raise RuntimeError(
            f"Could not find on-screen element: {element}. "
            "I tried accessibility, semantic text, OCR, and vision. "
            "If the button is visible, install Tesseract OCR and pywinauto, then try again."
        )

    def _click_resolved(self, el, frame, before_sig: Dict[str, Any], emit):
        emit(f"◆highlight {el.x} {el.y} {el.width} {el.height}")
        emit(f"Clicking {el.text}…")
        self.automation.capture_region = dict(self.vision.last_region)
        cx, cy = el.center
        self.automation.move_to(cx, cy)
        clicked = self.automation.click(cx, cy, label=el.text or "")
        time.sleep(0.7)
        after = self.vision.capture_screen()
        check = self.vision.frame_changed(frame, after, threshold=0.01)
        after_sig = page_snapshot()
        ok = click_succeeded(before_sig, after_sig, bool(check.get("changed")))
        if not ok:
            time.sleep(0.55)
            after = self.vision.capture_screen()
            check = self.vision.frame_changed(frame, after, threshold=0.01)
            after_sig = page_snapshot()
            ok = click_succeeded(before_sig, after_sig, bool(check.get("changed")))
        return clicked, check, after_sig, ok

    def _click_via_locate(self, element: str, prefer: str, frame, result: Dict[str, Any], emit) -> Dict[str, Any]:
        detection = self.vision.locate(element, prefer=prefer, frame=frame)
        result["detection"] = {
            "found": detection.found,
            "x": detection.x,
            "y": detection.y,
            "width": detection.width,
            "height": detection.height,
            "method": detection.method,
            "confidence": detection.confidence,
            "label": detection.label,
        }
        result["boxes"] = detection.boxes
        if not detection.found:
            self.automation.wait(0.25)
            frame = self.vision.capture_screen()
            self.automation.capture_region = dict(self.vision.last_region)
            detection = self.vision.locate(element, prefer=prefer, frame=frame)
            result["detection_retry"] = {
                "found": detection.found,
                "x": detection.x,
                "y": detection.y,
                "method": detection.method,
                "confidence": detection.confidence,
                "label": detection.label,
            }
            result["boxes"] = detection.boxes
            if not detection.found:
                result["capture_path"] = self.vision.save_capture(
                    frame, label=f"click_miss_{element}", boxes=detection.boxes
                )
                if self.automation.dry_run:
                    h, w = frame.shape[:2]
                    result["automation"] = self.automation.click(w // 2, h // 2, label=element)
                    result["note"] = "Element not found; dry-run used screen center"
                    return result
                raise RuntimeError(
                    f"Could not find on-screen element: {element}. "
                    "If the button is visible, install Tesseract OCR and try again."
                )
        result["capture_path"] = self.vision.save_capture(
            frame if frame is not None else self.vision.last_frame,
            label=f"click_hit_{element}",
            boxes=detection.boxes
            or [
                {
                    "x": detection.x - detection.width // 2,
                    "y": detection.y - detection.height // 2,
                    "w": detection.width or 8,
                    "h": detection.height or 8,
                    "label": detection.label or element,
                }
            ],
        )
        emit(f"Clicking “{detection.label or element}”")
        before_sig = page_snapshot()
        result["automation"] = self.automation.click(
            detection.x, detection.y, label=detection.label or element
        )
        if not self.automation.dry_run:
            time.sleep(0.45)
            after = self.vision.capture_screen()
            check = self.vision.frame_changed(frame, after, threshold=0.012)
            after_sig = page_snapshot()
            result["verification"] = check
            result["page_after"] = after_sig
            if not click_succeeded(before_sig, after_sig, bool(check.get("changed"))):
                emit("Click missed — retrying a bit lower")
                result["automation"] = self.automation.click(
                    detection.x, detection.y + 14, label=detection.label or element
                )
                time.sleep(0.45)
                after2 = self.vision.capture_screen()
                check2 = self.vision.frame_changed(frame, after2, threshold=0.012)
                result["verification_retry"] = check2
                result["page_after"] = page_snapshot()
        return result

    def _execute_step(
        self, step: Dict[str, Any], *, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        intent = step.get("intent", "unknown")
        entities = step.get("entities") or {}
        result: Dict[str, Any] = {"intent": intent, "entities": entities}

        if intent == "open_app":
            app = entities.get("app", "") or entities.get("query", "")
            try:
                result["automation"] = self.automation.open_app(app)
            except Exception:
                # Free-form: open whatever matches on disk
                result["automation"] = self.automation.find_and_open(
                    str(entities.get("query") or app)
                )
            follow = entities.get("follow_up")
            if follow:
                follow_parsed = self.nlp.parse(follow)
                for sub in follow_parsed.steps:
                    sub_res = self._execute_step(sub, user_id=user_id)
                    result.setdefault("follow_ups", []).append(sub_res)
            return result

        if intent == "open_file":
            path = entities.get("path")
            query = entities.get("query") or ""
            kind = entities.get("kind") or "any"
            if path:
                result["automation"] = self.automation.open_path(str(path))
            else:
                result["automation"] = self.automation.find_and_open(str(query), kind=str(kind))
            return result

        if intent == "type_text":
            typed = str(entities.get("text") or "")
            if is_sensitive_request(typed) or is_sensitive_request(str(entities.get("field") or "")):
                looks_placeholder = bool(
                    re.search(r"\b(my|the)\s+(password|pin|otp|code)\b", typed, re.I)
                    or typed.lower() in ("password", "my password", "the password", "otp", "pin")
                )
                if looks_placeholder:
                    result["needs_secret"] = True
                    result["confirm_prompt"] = "Enter the secret in the secure prompt. I will not log it."
                    return result
                result["automation"] = self.automation.type_text(typed)
                result["history"] = history_line_for_type(sensitive=True, field=str(entities.get("field") or ""))
                return result
            field = entities.get("field")
            if field:
                # Focus named field first (form-friendly)
                click_res = self._click_element(str(field), {"element": field})
                result["focus"] = click_res
                if click_res.get("capture_path"):
                    result["capture_path"] = click_res["capture_path"]
            result["automation"] = self.automation.type_text(entities.get("text", ""))
            return result

        if intent == "fill_form":
            field = str(entities.get("field") or "").strip()
            text = str(entities.get("text") or "")
            emit = getattr(self, "_status_cb", None) or (lambda _m: None)
            if field:
                emit(f"Filling form field “{field}”…")
                click_res = self._click_element(field, {"element": field})
                result["focus"] = click_res
                if click_res.get("capture_path"):
                    result["capture_path"] = click_res["capture_path"]
                result["boxes"] = click_res.get("boxes")
            else:
                emit("Typing into focused form field…")
            result["automation"] = self.automation.type_text(text)
            return result

        if intent == "press_key":
            result["automation"] = self.automation.press(entities.get("key", "enter"))
            return result

        if intent == "scroll":
            result["automation"] = self.automation.scroll(
                entities.get("direction", "down"),
                int(entities.get("amount", 3)),
            )
            return result

        if intent == "wait":
            result["automation"] = self.automation.wait(float(entities.get("seconds", 1)))
            return result

        if intent == "close_app":
            app = str(entities.get("app") or "").strip()
            if not app or app in ("__focused__", "the window", "this window", "current window", "window"):
                res = self.automation.close_focused_window()
                if res.get("blocked") and res.get("needs_confirm"):
                    result["needs_confirm"] = True
                    result["confirm_prompt"] = res["confirm_prompt"]
                result["automation"] = res
            else:
                res = self.automation.close_app(app)
                result["automation"] = res
                if res.get("status") == "waiting_for_user":
                    result["waiting_for_user"] = True
                    result["message"] = res.get("message", "")
                elif not res.get("success", False) and not self.automation.dry_run:
                    result["error"] = res.get("error") or res.get("message")
            return result

        if intent == "close_tab":
            result["automation"] = self.automation.press("ctrl+w")
            return result

        if intent == "minimize_window":
            app = str(entities.get("app") or "").strip()
            result["automation"] = self.automation.minimize_window(
                app if app not in ("__focused__", "the window", "this window", "window") else None
            )
            return result

        if intent == "restore_window":
            app = str(entities.get("app") or "").strip()
            result["automation"] = self.automation.restore_window(
                app if app not in ("__focused__", "the window", "this window", "window") else None
            )
            return result

        if intent in ("inspect_screen", "verify_screen"):
            result["note"] = "vision meta-step"
            return result

        if intent == "search_web":
            query = entities.get("query", "")
            q = str(query or "").strip()
            if q and " " not in q and "." in q:
                result["automation"] = apply_browser(self.automation, "OPEN_URL", {"url": q})
            else:
                result["automation"] = self.automation.search_google(query)
            return result

        if intent in (
            "open_url",
            "browser_back",
            "browser_forward",
            "browser_refresh",
            "new_tab",
            "switch_tab",
        ):
            kind = {
                "open_url": "OPEN_URL",
                "browser_back": "BACK",
                "browser_forward": "FORWARD",
                "browser_refresh": "REFRESH",
                "new_tab": "NEW_TAB",
                "switch_tab": "SWITCH_TAB",
            }[intent]
            result["automation"] = apply_browser(self.automation, kind, entities)
            return result

        if intent in ("start_task", "end_task", "emergency_stop"):
            result["note"] = intent
            return result

        if intent == "copy_file":
            result["automation"] = self.automation.copy_file(
                str(entities.get("source") or ""),
                str(entities.get("destination") or ""),
            )
            return result

        if intent == "move_file":
            result["automation"] = self.automation.move_file(
                str(entities.get("source") or ""),
                str(entities.get("destination") or ""),
            )
            return result

        if intent in ("click_text", "click_button"):
            element = entities.get("element", "")
            clicked = self._click_element(str(element), entities)
            clicked["intent"] = intent
            return clicked

        if intent == "run_workflow":
            name = entities.get("workflow", "")
            if user_id is None:
                raise RuntimeError("Login required to run workflows")
            nested = self.run_workflow_by_name(user_id, name)
            result["nested"] = nested
            if not nested.get("ok"):
                raise RuntimeError(nested.get("error") or "Workflow failed")
            return result

        raise RuntimeError(
            f"Unsupported intent: {intent}. Try open / copy / click / fill / type / search / run."
        )

    def capture_preview(self) -> Dict[str, Any]:
        frame = self.vision.capture_screen()
        self.last_frame = frame
        path = self.vision.save_capture(frame, label="preview")
        return {"frame": frame, "path": path, "boxes": [], "ok": self.vision.last_capture_ok}
