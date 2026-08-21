# import asyncio
# import itertools
# import json
# import os
# import re
# import sys
# from typing import Any, get_args, get_origin


# from browser_use import Agent
# from browser_use.llm.views import ChatInvokeCompletion


# # ==========================================================
# # NIZAM AGENT 1 — EXHAUSTIVE MULTI-PROVIDER LLM ADAPTER
# # ==========================================================

# BANNER_WIDTH = 64
# SPINNER_FRAMES = "|/-\\"
# PROGRESS_BAR_LEN = 30


# def _boxed(lines, width=BANNER_WIDTH):
#     """Render centered lines inside a plain-ASCII box (font/encoding safe)."""
#     top = "+" + "-" * (width - 2) + "+"
#     out = [top]
#     for line in lines:
#         inner = width - 2
#         pad_total = max(inner - len(line), 0)
#         left = pad_total // 2
#         right = pad_total - left
#         out.append("|" + " " * left + line + " " * right + "|")
#     out.append(top)
#     return "\n".join(out)


# def print_startup_banner(total_candidates):
#     banner = [
#         "",
#         "N I Z A M   A G E N T   1",
#         "",
#         "Exhaustive Multi-Provider Browser Agent",
#         f"{total_candidates} model sources loaded",
#         "",
#     ]
#     print()
#     print(_boxed(banner))
#     print()

# class G4FExhaustiveBrowserUseLLM:
#     """
#     Browser-use LLM adapter that discovers G4F's installed provider/model
#     registry at runtime and tests provider/model combinations until one
#     actually answers.

#     It intentionally does NOT use AnyProvider or model-router.

#     Discovery sources:
#       1. G4F ModelRegistry / __models__ when available.
#       2. Every provider exposed by g4f.Provider.__providers__.
#       3. Provider-declared model lists/default_model when available.

#     Providers/models that require authentication can be discovered and
#     tested, but failures are skipped. This means the agent does not stop
#     simply because one provider is unavailable.
#     """

#     provider = "Nizam Agent 1"

#     def __init__(self, model=None, temperature=0.2):
#         try:
#             import g4f
#             from g4f.client import Client
#         except Exception as e:
#             raise RuntimeError(
#                 "A required backend package is missing or outdated. "
#                 "Install/update it with: pip install -U g4f"
#             ) from e

#         self._g4f = g4f
#         self._Client = Client
#         self.temperature = temperature
#         self.model = model or os.getenv("G4F_MODEL", "").strip() or "auto-discovery"
#         self._last_provider = None
#         self._last_model = None
#         self._tested = set()
#         self._completed_count = 0
#         self._successful = None

#         # A true exhaustive scan can be very large. By default we test every
#         # discovered pair. Set G4F_MAX_CANDIDATES only if you intentionally
#         # want a cap.
#         cap = os.getenv("G4F_MAX_CANDIDATES", "").strip()
#         self._max_candidates = int(cap) if cap.isdigit() and int(cap) > 0 else None

#         self._candidates = self._discover_candidates()

#         if not self._candidates:
#             raise RuntimeError(
#                 "No usable model sources were discovered."
#             )

#     @property
#     def model_name(self):
#         return self._last_model or self.model

#     @property
#     def model_provider(self):
#         if self._last_provider and self._last_model:
#             return f"{self._last_provider} / {self._last_model}"
#         return "Nizam Agent 1 / auto-discovery"

#     @staticmethod
#     def _content_to_text(content):
#         if content is None:
#             return ""
#         if isinstance(content, str):
#             return content
#         if isinstance(content, list):
#             parts = []
#             for item in content:
#                 if isinstance(item, str):
#                     parts.append(item)
#                 elif isinstance(item, dict):
#                     value = item.get("text")
#                     if value:
#                         parts.append(str(value))
#                 else:
#                     value = getattr(item, "text", None)
#                     if value:
#                         parts.append(str(value))
#                     else:
#                         value = getattr(item, "value", None)
#                         if value:
#                             parts.append(str(value))
#             return "\n".join(parts)
#         return str(content)

#     def _convert_messages(self, messages):
#         converted = []
#         for message in messages:
#             message_type = type(message).__name__
#             content = self._content_to_text(getattr(message, "content", ""))

#             if message_type == "SystemMessage":
#                 role = "system"
#             elif message_type == "UserMessage":
#                 role = "user"
#             elif message_type == "AssistantMessage":
#                 role = "assistant"
#             else:
#                 role = getattr(message, "role", None) or "user"

#             converted.append({"role": role, "content": content})
#         return converted

#     @staticmethod
#     def _extract_json(text):
#         if not text:
#             return None

#         text = text.strip()
#         text = re.sub(
#             r"^```(?:json)?\s*|\s*```$",
#             "",
#             text,
#             flags=re.IGNORECASE | re.DOTALL,
#         ).strip()

#         try:
#             return json.loads(text)
#         except Exception:
#             pass

#         decoder = json.JSONDecoder()
#         for index, char in enumerate(text):
#             if char != "{":
#                 continue
#             try:
#                 obj, _ = decoder.raw_decode(text[index:])
#                 return obj
#             except Exception:
#                 continue

#         return None

#     @staticmethod
#     def _extract_g4f_text(response):
#         try:
#             choices = getattr(response, "choices", None)
#             if choices:
#                 message = getattr(choices[0], "message", None)
#                 content = getattr(message, "content", None)
#                 if content:
#                     return str(content).strip()
#         except Exception:
#             pass

#         if isinstance(response, dict):
#             try:
#                 choices = response.get("choices") or []
#                 if choices:
#                     message = choices[0].get("message", {})
#                     content = message.get("content")
#                     if content:
#                         return str(content).strip()
#             except Exception:
#                 pass

#         return ""

#     @staticmethod
#     def _provider_name(provider):
#         return (
#             getattr(provider, "label", None)
#             or getattr(provider, "__name__", None)
#             or str(provider)
#         )

#     def _provider_registry(self):
#         providers = []

#         try:
#             registry = getattr(self._g4f.Provider, "__providers__", None)
#             if registry:
#                 providers.extend(registry)
#         except Exception:
#             pass

#         try:
#             names = getattr(self._g4f.Provider, "__all__", [])
#             for name in names:
#                 if name in {
#                     "BaseProvider", "ProviderType", "RetryProvider",
#                     "IterListProvider", "RotatedProvider",
#                     "AsyncProvider", "AsyncGeneratorProvider",
#                     "CreateImagesProvider", "ProviderUtils", "__providers__",
#                     "__map__",
#                 }:
#                     continue
#                 try:
#                     provider = getattr(self._g4f.Provider, name)
#                     if provider not in providers:
#                         providers.append(provider)
#                 except Exception:
#                     continue

#         except Exception:
#             pass

#         return providers

#     @staticmethod
#     def _model_names_from_provider(provider):
#         result = []

#         for attr in ("models", "model_names"):
#             try:
#                 values = getattr(provider, attr, None)
#                 if isinstance(values, str):
#                     values = [values]
#                 if values:
#                     result.extend(str(x) for x in values if x)
#             except Exception:
#                 pass

#         for attr in ("default_model", "default_vision_model"):
#             try:
#                 value = getattr(provider, attr, None)
#                 if value:
#                     result.append(str(value))
#             except Exception:
#                 pass

#         return list(dict.fromkeys(result))

#     def _registry_model_provider_pairs(self):
#         pairs = []

#         # Current G4F ModelRegistry/__models__.
#         try:
#             models_module = __import__("g4f.models", fromlist=["__models__"])
#             registry = getattr(models_module, "__models__", {})
#             for model_name, entry in registry.items():
#                 try:
#                     _model, providers = entry
#                 except Exception:
#                     continue

#                 for provider in providers or []:
#                     if isinstance(provider, str):
#                         pairs.append((provider, model_name))
#                     else:
#                         pairs.append(
#                             (self._provider_name(provider), model_name)
#                         )
#         except Exception:
#             pass

#         return pairs

#     def _discover_candidates(self):
#         candidates = []

#         # 1. Explicit G4F model registry mappings.
#         candidates.extend(self._registry_model_provider_pairs())

#         # 2. Every provider and every model advertised by that provider.
#         for provider in self._provider_registry():
#             provider_name = self._provider_name(provider)
#             models = self._model_names_from_provider(provider)

#             # If a provider doesn't advertise a model, its default_model
#             # may still be usable.
#             for model_name in models:
#                 candidates.append((provider_name, model_name))

#         # 3. If G4F_MODEL is explicitly supplied, prioritize that model
#         # across every discovered provider. This still checks all providers.
#         forced_model = os.getenv("G4F_MODEL", "").strip()
#         if forced_model:
#             provider_names = [
#                 self._provider_name(p)
#                 for p in self._provider_registry()
#             ]
#             candidates = (
#                 [(p, forced_model) for p in provider_names]
#                 + candidates
#             )

#         # Remove impossible routing pseudo-providers.
#         blocked = {
#             "AnyProvider",
#             "G4FSpace",
#         }

#         cleaned = []
#         seen = set()

#         for provider_name, model_name in candidates:
#             provider_name = str(provider_name)
#             model_name = str(model_name)

#             if not provider_name or not model_name:
#                 continue
#             if provider_name in blocked:
#                 continue

#             key = (provider_name, model_name)
#             if key not in seen:
#                 seen.add(key)
#                 cleaned.append(key)

#         # Prefer commonly free/anonymous providers first, but do NOT remove
#         # anything. The user asked for exhaustive checking.
#         preferred = {
#             "Pollinations": 0,
#             "Gemini": 1,
#             "GeminiPro": 2,
#             "DeepInfra": 3,
#             "HuggingSpace": 4,
#             "HuggingChat": 5,
#             "Qwen": 6,
#             "Together": 7,
#             "TeachAnything": 8,
#         }

#         cleaned.sort(key=lambda x: (preferred.get(x[0], 100), x[0], x[1]))

#         if self._max_candidates:
#             return cleaned[:self._max_candidates]

#         return cleaned

#     def _resolve_provider(self, provider_name):
#         try:
#             return getattr(self._g4f.Provider, provider_name)
#         except Exception as e:
#             raise RuntimeError(
#                 f"Provider '{provider_name}' is unavailable."
#             ) from e

#     def _request_with_provider(self, provider_name, model, messages):
#         provider = self._resolve_provider(provider_name)
#         client = self._Client(provider=provider)

#         kwargs = {
#             "model": model,
#             "messages": messages,
#             "stream": False,
#             "temperature": self.temperature,
#         }

#         try:
#             return client.chat.completions.create(**kwargs)
#         except TypeError:
#             kwargs.pop("temperature", None)
#             return client.chat.completions.create(**kwargs)

#     def _request_one(self, index, provider_name, model, messages):
#         """
#         Execute exactly one provider/model request.

#         Each candidate gets its own G4F Client instance so the requests can
#         safely be executed in parallel threads.
#         """
#         key = (provider_name, model)

#         try:
#             response = self._request_with_provider(
#                 provider_name,
#                 model,
#                 messages,
#             )

#             text = self._extract_g4f_text(response)

#             if not text:
#                 raise RuntimeError("empty response")

#             return {
#                 "ok": True,
#                 "provider": provider_name,
#                 "model": model,
#                 "response": response,
#                 "text": text,
#                 "error": None,
#                 "key": key,
#             }

#         except Exception as e:
#             error_text = f"{type(e).__name__}: {e}"

#             return {
#                 "ok": False,
#                 "provider": provider_name,
#                 "model": model,
#                 "response": None,
#                 "text": "",
#                 "error": error_text,
#                 "key": key,
#             }

#         finally:
#             self._completed_count += 1

#     async def _request_all_concurrently(self, messages):
#         """
#         Launch EVERY discovered provider/model combination concurrently.

#         We do not wait for provider A before starting provider B.

#         The caller receives all completed responses so ainvoke() can choose
#         the first response that is actually valid for Browser Use's schema.

#         NOTE: self._tested is reset at the top of every call. Browser-use
#         invokes this adapter once per agent step, and each step needs its
#         own full scan of every discovered provider/model combination --
#         otherwise, once one step exhausts the candidate list, every later
#         step would immediately fail with "already tested" and the agent
#         could never recover from a bad pick.
#         """

#         self._tested = set()

#         candidates = [
#             (index, provider_name, model)
#             for index, (provider_name, model)
#             in enumerate(self._candidates, 1)
#             if (provider_name, model) not in self._tested
#         ]

#         if not candidates:
#             raise RuntimeError(
#                 "All discovered provider/model combinations have already "
#                 "been tested."
#             )

#         # Mark them before launching. This prevents duplicate launches if
#         # browser-use invokes the same LLM object again within this call.
#         for _, provider_name, model in candidates:
#             self._tested.add((provider_name, model))

#         self._completed_count = 0

#         tasks = [
#             asyncio.to_thread(
#                 self._request_one,
#                 index,
#                 provider_name,
#                 model,
#                 messages,
#             )
#             for index, provider_name, model in candidates
#         ]

#         progress_task = asyncio.create_task(
#             self._report_progress(len(candidates))
#         )

#         # return_exceptions=True is important: one dead provider must never
#         # cancel the other provider/model requests.
#         results = await asyncio.gather(
#             *tasks,
#             return_exceptions=True,
#         )

#         self._completed_count = len(candidates)
#         await progress_task

#         normalized = []

#         for candidate, result in zip(candidates, results):
#             index, provider_name, model = candidate

#             if isinstance(result, Exception):
#                 normalized.append({
#                     "ok": False,
#                     "provider": provider_name,
#                     "model": model,
#                     "response": None,
#                     "text": "",
#                     "error": (
#                         f"{type(result).__name__}: {result}"
#                     ),
#                     "key": (provider_name, model),
#                 })
#             else:
#                 normalized.append(result)

#         success_count = sum(
#             1 for result in normalized if result["ok"]
#         )

#         print(
#             f"  {success_count}/{len(normalized)} model sources responded."
#         )

#         return normalized

#     async def _report_progress(self, total):
#         """Live single-line progress bar shown while every candidate is
#         queried concurrently, replacing a per-candidate print log."""

#         if total <= 0:
#             return

#         frames = itertools.cycle(SPINNER_FRAMES)

#         while self._completed_count < total:
#             frame = next(frames)
#             filled = int(PROGRESS_BAR_LEN * self._completed_count / total)
#             bar = "#" * filled + "-" * (PROGRESS_BAR_LEN - filled)
#             pct = int(100 * self._completed_count / total)
#             sys.stdout.write(
#                 f"\r  {frame} Scanning models  [{bar}] "
#                 f"{self._completed_count:>4}/{total} ({pct:>3}%)  "
#             )
#             sys.stdout.flush()
#             await asyncio.sleep(0.08)

#         bar = "#" * PROGRESS_BAR_LEN
#         sys.stdout.write(
#             f"\r  * Scan complete   [{bar}] {total:>4}/{total} (100%)  \n"
#         )
#         sys.stdout.flush()

#     def _validate_and_repair_output(self, text, output_format):
#         """
#         Convert a raw G4F response into Browser Use's expected Pydantic
#         output. Returns the validated model or None.
#         """

#         data = self._extract_json(text)

#         if not isinstance(data, dict):
#             return None

#         try:
#             return output_format.model_validate(data)

#         except Exception:
#             action = data.get("action")

#             if not isinstance(action, list):
#                 return None

#             try:
#                 action_candidates = self._get_action_candidates(
#                     output_format
#                 )

#                 repaired_actions, changed = self._repair_action_list(
#                     action,
#                     action_candidates,
#                 )

#                 if not changed:
#                     return None

#                 data["action"] = repaired_actions

#                 return output_format.model_validate(data)

#             except Exception:
#                 return None

#     async def _request(self, messages, output_format=None):
#         """
#         Concurrently query all discovered candidates and select the first
#         response that is usable.

#         If a Browser Use output schema is supplied, "usable" means the
#         response successfully parses AND validates against that schema.
#         This is stronger than merely checking that a provider returned text.

#         Candidates are evaluated in the adapter's canonical candidate order
#         (see _discover_candidates), NOT in whatever order they happened to
#         finish -- so this picks the first candidate that actually produces
#         a schema-valid, actionable response, rather than whichever provider
#         merely answered fastest.
#         """

#         results = await self._request_all_concurrently(messages)

#         # Browser Use structured output:
#         # select the first provider/model whose response validates correctly.
#         if output_format is not None:
#             for result in results:
#                 if not result["ok"]:
#                     continue

#                 parsed = self._validate_and_repair_output(
#                     result["text"],
#                     output_format,
#                 )

#                 if parsed is not None:
#                     self._last_provider = result["provider"]
#                     self._last_model = result["model"]
#                     self._successful = result["key"]

#                     print(
#                         f"  -> Using {result['provider']} / "
#                         f"{result['model']}"
#                     )

#                     return result, parsed

#             errors = [
#                 (
#                     f"{r['provider']}/{r['model']}: "
#                     f"{r['error']}"
#                 )
#                 for r in results
#                 if not r["ok"]
#             ]

#             raise RuntimeError(
#                 "All concurrent requests failed schema validation "
#                 "or failed to respond.\n"
#                 + "\n".join(f"  - {x}" for x in errors)
#             )

#         # Non-structured response: select first usable text.
#         for result in results:
#             if result["ok"] and result["text"]:
#                 self._last_provider = result["provider"]
#                 self._last_model = result["model"]
#                 self._successful = result["key"]

#                 print(
#                     f"  -> Using {result['provider']} / {result['model']}"
#                 )

#                 return result, result["text"]

#         raise RuntimeError(
#             "All concurrent requests failed."
#         )

#     async def ainvoke(
#         self,
#         messages,
#         output_format=None,
#         request_type="browser_agent",
#         **kwargs: Any,
#     ):
#         lc_messages = self._convert_messages(messages)

#         if output_format is not None:
#             schema = output_format.model_json_schema()

#             schema_instruction = (
#                 "\n\nIMPORTANT: Return ONLY valid JSON. "
#                 "Do not use markdown fences or explanatory text. "
#                 "The JSON MUST conform exactly to this schema:\n"
#                 + json.dumps(schema, ensure_ascii=False)
#             )

#             if lc_messages:
#                 lc_messages = list(lc_messages)
#                 lc_messages[-1] = dict(lc_messages[-1])
#                 lc_messages[-1]["content"] = (
#                     str(lc_messages[-1].get("content", ""))
#                     + schema_instruction
#                 )

#         selected, parsed_result = await self._request(
#             lc_messages,
#             output_format=output_format,
#         )

#         if output_format is None:
#             return ChatInvokeCompletion(
#                 completion=parsed_result,
#                 usage=None,
#             )

#         # parsed_result has already been validated against output_format
#         # by _request(), so Browser Use receives the selected model's
#         # structured response directly.
#         return ChatInvokeCompletion(
#             completion=parsed_result,
#             usage=None,
#         )

#     def _get_action_candidates(self, output_format):
#         try:
#             action_annotation = (
#                 output_format.model_fields["action"].annotation
#             )
#         except Exception:
#             return []

#         outer_args = get_args(action_annotation)
#         candidates = []

#         for arg in outer_args:
#             inner_args = get_args(arg)
#             candidates.extend(inner_args if inner_args else [arg])

#         return [
#             c for c in candidates
#             if hasattr(c, "model_fields")
#         ]

#     def _find_action_field(self, action_candidates, key):
#         for candidate in action_candidates:
#             field = candidate.model_fields.get(key)
#             if field is not None:
#                 return field
#         return None

#     def _repair_action_list(self, action_list, action_candidates):
#         repaired = []
#         changed = False

#         for item in action_list:
#             if not isinstance(item, dict) or len(item) != 1:
#                 repaired.append(item)
#                 continue

#             (key, value), = item.items()
#             field = self._find_action_field(action_candidates, key)

#             if field is None:
#                 repaired.append(item)
#                 continue

#             sub_model = field.annotation
#             origin = get_origin(sub_model)

#             if origin is not None:
#                 inner = [
#                     a for a in get_args(sub_model)
#                     if a is not type(None)
#                 ]
#                 if inner:
#                     sub_model = inner[0]

#             if not hasattr(sub_model, "model_fields"):
#                 repaired.append(item)
#                 continue

#             required_fields = [
#                 fname
#                 for fname, finfo in sub_model.model_fields.items()
#                 if finfo.is_required()
#             ]

#             if not isinstance(value, dict):
#                 if len(required_fields) == 1:
#                     repaired.append({
#                         key: {required_fields[0]: value}
#                     })
#                     changed = True
#                 else:
#                     repaired.append(item)
#                 continue

#             valid_keys = set(sub_model.model_fields.keys())

#             if set(value.keys()) <= valid_keys:
#                 repaired.append(item)
#                 continue

#             if len(required_fields) == 1 and len(value) == 1:
#                 ((_wrong_key, only_val),) = value.items()
#                 repaired.append({
#                     key: {required_fields[0]: only_val}
#                 })
#                 changed = True
#             else:
#                 repaired.append(item)

#         return repaired, changed


# # ==========================================================
# # LLM
# # ==========================================================

# llm = G4FExhaustiveBrowserUseLLM(
#     model=os.getenv("G4F_MODEL") or None,
#     temperature=0.2,
# )

# # ==========================================================
# # TERMINAL ACCESS
# #
# # Gives the agent a shell/terminal action it can call as a normal tool,
# # alongside its browser actions. Every command runs with its working
# # directory fixed to the folder this script lives in.
# #
# # NOTE on scope: fixing cwd only sets the *starting* directory for the
# # command. A command that itself does `cd ..` or references an absolute
# # path elsewhere is not blocked -- there is no filesystem sandbox/chroot
# # here, just a scoped starting point. Only run this with tasks you trust.
# # ==========================================================

# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# def _build_controller():
#     """
#     Register a terminal-command action on a browser-use Controller.

#     Returns None (instead of raising) if the installed browser-use version
#     doesn't expose Controller/actions the way this code expects, so the
#     agent still runs in browser-only mode rather than crashing on startup.
#     """

#     try:
#         from browser_use import Controller
#     except Exception as e:
#         print(f"  Terminal-access tool unavailable (no Controller): {e}")
#         return None

#     ActionResult = None
#     for path in (
#         "browser_use.agent.views",
#         "browser_use",
#     ):
#         try:
#             module = __import__(path, fromlist=["ActionResult"])
#             ActionResult = getattr(module, "ActionResult", None)
#             if ActionResult is not None:
#                 break
#         except Exception:
#             continue

#     try:
#         controller = Controller()

#         @controller.action(
#             "Run a shell/terminal command. It always starts in the "
#             f"agent's own working folder ({SCRIPT_DIR}). Use this for "
#             "file operations, running local scripts, checking installed "
#             "tools, or anything else that needs a real terminal instead "
#             "of a browser."
#         )
#         def run_terminal_command(command: str):
#             import subprocess

#             try:
#                 completed = subprocess.run(
#                     command,
#                     shell=True,
#                     cwd=SCRIPT_DIR,
#                     capture_output=True,
#                     text=True,
#                     timeout=120,
#                 )
#                 output = (
#                     (completed.stdout or "") + (completed.stderr or "")
#                 ).strip()
#                 if not output:
#                     output = (
#                         f"(command exited with code {completed.returncode}, "
#                         "no output)"
#                     )
#                 output = output[:4000]
#             except subprocess.TimeoutExpired:
#                 output = "Command timed out after 120 seconds."
#             except Exception as e:
#                 output = f"Command failed: {type(e).__name__}: {e}"

#             if ActionResult is not None:
#                 try:
#                     return ActionResult(
#                         extracted_content=output,
#                         include_in_memory=True,
#                     )
#                 except TypeError:
#                     return ActionResult(extracted_content=output)

#             return output

#         return controller

#     except Exception as e:
#         print(f"  Terminal-access tool unavailable: {e}")
#         return None


# # ==========================================================
# # PERSISTENCE GUIDANCE
# #
# # Left to itself the agent tends to take the easy way out: hit one
# # obstacle (a login wall, an ambiguous name) and immediately end the
# # task by asking the user a clarifying question -- even when it
# # already found the concrete answer (e.g. a real profile URL) and
# # just didn't report it. This nudges it to keep trying reasonable
# # alternate strategies and to only finish once it has something
# # concrete and verifiable, not before.
# # ==========================================================

# AGENT_PERSISTENCE_GUIDANCE = (
#     "Persistence and completion policy: "
#     "When the task requires finding specific, verifiable information "
#     "(such as a person's profile, a document, or a piece of data), do "
#     "not stop and ask the user a clarifying question while reasonable, "
#     "untried strategies remain. Before giving up, try alternate search "
#     "phrasings, common alternate spellings, other search engines, and "
#     "extracting URLs directly from search result links (e.g. via the "
#     "extract action, or by reading link hrefs from the page) instead "
#     "of only opening pages that require a login. "
#     "If you find candidate results, prefer extracting and reporting "
#     "the concrete details (such as the actual URL) over describing "
#     "them in vague prose. "
#     "You also have a terminal-command action available, scoped to your "
#     "own working folder -- use it for local file work, running scripts, "
#     "or checking installed tools whenever that's a better fit than the "
#     "browser. "
#     "Only call `done` with success=true once you have concrete, "
#     "verifiable evidence for the answer. Only call `done` with "
#     "success=false after you have exhausted the reasonable strategies "
#     "available to you, and explain specifically what you tried and "
#     "why each attempt did not resolve the task."
# )


# def build_agent(task, controller=None):
#     """
#     Construct the browser-use Agent with persistence guidance, terminal
#     access, and a higher failure budget, falling back gracefully if the
#     installed browser-use version doesn't support one of these kwargs.
#     """

#     base_kwargs = dict(
#         task=task,
#         llm=llm,
#         use_vision=True,
#         max_actions_per_step=10,
#     )

#     controller_kwargs = (
#         dict(controller=controller) if controller is not None else {}
#     )

#     optional_kwarg_sets = [
#         dict(
#             **controller_kwargs,
#             extend_system_message=AGENT_PERSISTENCE_GUIDANCE,
#             max_failures=8,
#         ),
#         dict(**controller_kwargs, extend_system_message=AGENT_PERSISTENCE_GUIDANCE),
#         dict(**controller_kwargs, max_failures=8),
#         dict(**controller_kwargs),
#         # If the controller kwarg itself isn't accepted by this browser-use
#         # version, fall back further to browser-only mode rather than
#         # failing to start the agent at all.
#         dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE, max_failures=8),
#         dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE),
#         dict(max_failures=8),
#         dict(),
#     ]

#     last_error = None

#     for extra_kwargs in optional_kwarg_sets:
#         try:
#             agent = Agent(**base_kwargs, **extra_kwargs)

#             if extra_kwargs:
#                 print(f"  Agent options: {list(extra_kwargs)}")

#             return agent

#         except TypeError as e:
#             last_error = e
#             continue

#     raise last_error


# async def run_agent(agent):
#     """
#     Run the agent with a larger step budget when supported, falling
#     back to the default if this browser-use version doesn't accept
#     max_steps on run().
#     """

#     try:
#         return await agent.run(max_steps=50)
#     except TypeError:
#         return await agent.run()


# # ==========================================================
# # TASK INPUT
# # ==========================================================

# def get_ui_task():

#     task = os.getenv("AGENT_TASK", "").strip()

#     if task:
#         return task

#     try:
#         if not sys.stdin.isatty():
#             data = sys.stdin.read().strip()
#             if data:
#                 return data
#     except Exception:
#         pass

#     return ""


# # ==========================================================
# # MAIN
# #
# # Runs as a persistent loop: it never exits after a single task.
# # Once one task finishes (or fails), it asks for the next one. Type
# # 'exit' / 'quit', or press Ctrl+C, to actually stop the process.
# # ==========================================================

# async def main():

#     print_startup_banner(len(llm._candidates))
#     print(_boxed(["Terminal access folder:", SCRIPT_DIR[:BANNER_WIDTH - 6]]))

#     controller = _build_controller()

#     print(_boxed(["Persistent mode: running until you type 'exit'"]))

#     # Only the very first task may come from AGENT_TASK / piped stdin.
#     # Every task after that is asked for interactively -- otherwise a
#     # fixed AGENT_TASK env var or an exhausted stdin pipe would either
#     # loop forever on the same task or spin with nothing to do.
#     pending_task = get_ui_task()

#     while True:
#         if pending_task:
#             task = pending_task
#             pending_task = None
#         else:
#             try:
#                 task = input(
#                     "\nEnter the next task (or 'exit' to quit):\n> "
#                 ).strip()
#             except (EOFError, KeyboardInterrupt):
#                 print("\n\nShutting down.")
#                 break

#         if not task:
#             continue

#         if task.lower() in {"exit", "quit"}:
#             print("\nShutting down.")
#             break

#         print("\nTask received. Starting agent...\n")

#         try:
#             agent = build_agent(task, controller=controller)
#             result = await run_agent(agent)

#             print()
#             print(_boxed(["FINAL RESULT"]))
#             print(result)

#         except Exception as e:
#             print()
#             print(_boxed(["AGENT ERROR", "", repr(e)[:BANNER_WIDTH - 6]]))
#             print("  Continuing -- ready for the next task.")


# if __name__ == "__main__":
#     asyncio.run(main())






























# import asyncio
# import itertools
# import json
# import os
# import re
# import sys
# from typing import Any, get_args, get_origin


# from browser_use import Agent

# try:
#     from browser_use import Tools as Controller
# except ImportError:
#     from browser_use import Controller

# from browser_use.llm.views import ChatInvokeCompletion


# # ==========================================================
# # NIZAM AGENT 1 — EXHAUSTIVE MULTI-PROVIDER LLM ADAPTER
# # ==========================================================

# BANNER_WIDTH = 64
# SPINNER_FRAMES = "|/-\\"
# PROGRESS_BAR_LEN = 30

# # Providers known to accept OpenAI-style multimodal ("image_url") content
# # blocks in their chat messages. This list is intentionally conservative --
# # it is only used to decide which candidates get a real screenshot instead
# # of a text-only fallback. Everything else still gets tried, just without
# # the image attached, so nothing is excluded from the exhaustive scan.
# VISION_CAPABLE_PROVIDERS = {
#     "Gemini",
#     "GeminiPro",
#     "HuggingSpace",
#     "HuggingChat",
#     "PollinationsAI",
#     "Pollinations",
#     "OpenaiChat",
#     "Blackbox",
#     "Qwen",
#     "DeepInfra",
#     "Together",
#     "CopilotAccount",
#     "MetaAI",
# }


# def _boxed(lines, width=BANNER_WIDTH):
#     """Render centered lines inside a plain-ASCII box (font/encoding safe)."""
#     top = "+" + "-" * (width - 2) + "+"
#     out = [top]
#     for line in lines:
#         inner = width - 2
#         pad_total = max(inner - len(line), 0)
#         left = pad_total // 2
#         right = pad_total - left
#         out.append("|" + " " * left + line + " " * right + "|")
#     out.append(top)
#     return "\n".join(out)


# def print_startup_banner(total_candidates):
#     banner = [
#         "",
#         "N I Z A M   A G E N T   1",
#         "",
#         "Exhaustive Multi-Provider Browser Agent",
#         f"{total_candidates} model sources loaded",
#         "",
#     ]
#     print()
#     print(_boxed(banner))
#     print()

# class G4FExhaustiveBrowserUseLLM:
#     """
#     Browser-use LLM adapter that discovers G4F's installed provider/model
#     registry at runtime and tests provider/model combinations until one
#     actually answers.

#     It intentionally does NOT use AnyProvider or model-router.

#     Discovery sources:
#       1. G4F ModelRegistry / __models__ when available.
#       2. Every provider exposed by g4f.Provider.__providers__.
#       3. Provider-declared model lists/default_model when available.

#     Providers/models that require authentication can be discovered and
#     tested, but failures are skipped. This means the agent does not stop
#     simply because one provider is unavailable.

#     Vision: browser-use sends multimodal messages (a text part plus one or
#     more image_url parts, e.g. screenshots) whenever the Agent is built
#     with use_vision=True. This adapter now forwards those image blocks
#     as real OpenAI-style multimodal content to providers believed to
#     support vision (see VISION_CAPABLE_PROVIDERS), instead of silently
#     discarding them. For every other provider -- and as an automatic
#     fallback if a multimodal call fails -- it falls back to a text-only
#     call with a short marker noting an image was omitted, so the scan
#     stays exhaustive and never hard-fails just because one candidate
#     can't see images.
#     """

#     provider = "Nizam Agent 1"

#     def __init__(self, model=None, temperature=0.2):
#         try:
#             import g4f
#             from g4f.client import Client
#         except Exception as e:
#             raise RuntimeError(
#                 "A required backend package is missing or outdated. "
#                 "Install/update it with: pip install -U g4f"
#             ) from e

#         self._g4f = g4f
#         self._Client = Client
#         self.temperature = temperature
#         self.model = model or os.getenv("G4F_MODEL", "").strip() or "auto-discovery"
#         self._last_provider = None
#         self._last_model = None
#         self._tested = set()
#         self._completed_count = 0
#         self._successful = None

#         # A true exhaustive scan can be very large. By default we test every
#         # discovered pair. Set G4F_MAX_CANDIDATES only if you intentionally
#         # want a cap.
#         cap = os.getenv("G4F_MAX_CANDIDATES", "").strip()
#         self._max_candidates = int(cap) if cap.isdigit() and int(cap) > 0 else None

#         self._candidates = self._discover_candidates()

#         if not self._candidates:
#             raise RuntimeError(
#                 "No usable model sources were discovered."
#             )

#     @property
#     def model_name(self):
#         return self._last_model or self.model

#     @property
#     def model_provider(self):
#         if self._last_provider and self._last_model:
#             return f"{self._last_provider} / {self._last_model}"
#         return "Nizam Agent 1 / auto-discovery"

#     @staticmethod
#     def _content_to_text(content):
#         """Text-only rendering of a message's content (used for the
#         text-only fallback path, and for providers we don't believe
#         support vision)."""
#         if content is None:
#             return ""
#         if isinstance(content, str):
#             return content
#         if isinstance(content, list):
#             parts = []
#             for item in content:
#                 if isinstance(item, str):
#                     parts.append(item)
#                 elif isinstance(item, dict):
#                     item_type = item.get("type")
#                     if item_type in ("image_url", "image"):
#                         parts.append("[image omitted - provider is text-only]")
#                         continue
#                     value = item.get("text")
#                     if value:
#                         parts.append(str(value))
#                 else:
#                     value = getattr(item, "text", None)
#                     if value:
#                         parts.append(str(value))
#                     else:
#                         image_val = getattr(item, "image_url", None) or getattr(
#                             item, "image", None
#                         )
#                         if image_val is not None:
#                             parts.append(
#                                 "[image omitted - provider is text-only]"
#                             )
#                             continue
#                         value = getattr(item, "value", None)
#                         if value:
#                             parts.append(str(value))
#             return "\n".join(parts)
#         return str(content)

#     @staticmethod
#     def _extract_image_url(item):
#         """Best-effort extraction of a usable image URL/data-URI from a
#         single content block, regardless of whether it's a dict or an
#         object (browser-use's ContentPartImageParam or similar)."""
#         if isinstance(item, dict):
#             image_url = item.get("image_url")
#             if isinstance(image_url, dict):
#                 return image_url.get("url")
#             if isinstance(image_url, str):
#                 return image_url
#             image = item.get("image")
#             if isinstance(image, str):
#                 return image
#             return None

#         image_url = getattr(item, "image_url", None)
#         if image_url is not None:
#             url = getattr(image_url, "url", None)
#             if url:
#                 return url
#             if isinstance(image_url, str):
#                 return image_url

#         image = getattr(item, "image", None)
#         if isinstance(image, str):
#             return image

#         return None

#     @classmethod
#     def _content_to_multimodal(cls, content):
#         """
#         Render a message's content as OpenAI-style multimodal content
#         blocks (list of {"type": "text"/"image_url", ...}) so a
#         vision-capable provider actually receives the screenshot,
#         instead of only the text browser-use attached alongside it.

#         Returns a plain string if there are no image parts (nothing
#         multimodal to send), or a list of content blocks if there is
#         at least one image.
#         """
#         if content is None:
#             return ""
#         if isinstance(content, str):
#             return content
#         if not isinstance(content, list):
#             return str(content)

#         blocks = []
#         has_image = False

#         for item in content:
#             if isinstance(item, str):
#                 if item:
#                     blocks.append({"type": "text", "text": item})
#                 continue

#             image_url = cls._extract_image_url(item)
#             if image_url:
#                 has_image = True
#                 blocks.append(
#                     {"type": "image_url", "image_url": {"url": image_url}}
#                 )
#                 continue

#             text_val = None
#             if isinstance(item, dict):
#                 text_val = item.get("text")
#             else:
#                 text_val = getattr(item, "text", None)

#             if text_val:
#                 blocks.append({"type": "text", "text": str(text_val)})

#         if not has_image:
#             # Nothing visual in this message -- a plain string is simpler
#             # and works with every provider, vision-capable or not.
#             return "\n".join(b["text"] for b in blocks if b.get("type") == "text")

#         return blocks

#     def _convert_messages(self, messages, multimodal=False):
#         """
#         Convert browser-use's internal message objects into plain
#         OpenAI-style dicts.

#         multimodal=True preserves image_url content blocks (for
#         providers we're sending real vision to); multimodal=False
#         collapses everything to text (safe default / fallback path).
#         """
#         converted = []
#         for message in messages:
#             message_type = type(message).__name__
#             raw_content = getattr(message, "content", "")

#             if multimodal:
#                 content = self._content_to_multimodal(raw_content)
#             else:
#                 content = self._content_to_text(raw_content)

#             if message_type == "SystemMessage":
#                 role = "system"
#             elif message_type == "UserMessage":
#                 role = "user"
#             elif message_type == "AssistantMessage":
#                 role = "assistant"
#             else:
#                 role = getattr(message, "role", None) or "user"

#             converted.append({"role": role, "content": content})
#         return converted

#     @staticmethod
#     def _extract_json(text):
#         if not text:
#             return None

#         text = text.strip()
#         text = re.sub(
#             r"^```(?:json)?\s*|\s*```$",
#             "",
#             text,
#             flags=re.IGNORECASE | re.DOTALL,
#         ).strip()

#         try:
#             return json.loads(text)
#         except Exception:
#             pass

#         decoder = json.JSONDecoder()
#         for index, char in enumerate(text):
#             if char != "{":
#                 continue
#             try:
#                 obj, _ = decoder.raw_decode(text[index:])
#                 return obj
#             except Exception:
#                 continue

#         return None

#     @staticmethod
#     def _extract_g4f_text(response):
#         try:
#             choices = getattr(response, "choices", None)
#             if choices:
#                 message = getattr(choices[0], "message", None)
#                 content = getattr(message, "content", None)
#                 if content:
#                     return str(content).strip()
#         except Exception:
#             pass

#         if isinstance(response, dict):
#             try:
#                 choices = response.get("choices") or []
#                 if choices:
#                     message = choices[0].get("message", {})
#                     content = message.get("content")
#                     if content:
#                         return str(content).strip()
#             except Exception:
#                 pass

#         return ""

#     @staticmethod
#     def _provider_name(provider):
#         return (
#             getattr(provider, "label", None)
#             or getattr(provider, "__name__", None)
#             or str(provider)
#         )

#     def _provider_registry(self):
#         providers = []

#         try:
#             registry = getattr(self._g4f.Provider, "__providers__", None)
#             if registry:
#                 providers.extend(registry)
#         except Exception:
#             pass

#         try:
#             names = getattr(self._g4f.Provider, "__all__", [])
#             for name in names:
#                 if name in {
#                     "BaseProvider", "ProviderType", "RetryProvider",
#                     "IterListProvider", "RotatedProvider",
#                     "AsyncProvider", "AsyncGeneratorProvider",
#                     "CreateImagesProvider", "ProviderUtils", "__providers__",
#                     "__map__",
#                 }:
#                     continue
#                 try:
#                     provider = getattr(self._g4f.Provider, name)
#                     if provider not in providers:
#                         providers.append(provider)
#                 except Exception:
#                     continue

#         except Exception:
#             pass

#         return providers

#     @staticmethod
#     def _model_names_from_provider(provider):
#         result = []

#         for attr in ("models", "model_names"):
#             try:
#                 values = getattr(provider, attr, None)
#                 if isinstance(values, str):
#                     values = [values]
#                 if values:
#                     result.extend(str(x) for x in values if x)
#             except Exception:
#                 pass

#         for attr in ("default_model", "default_vision_model"):
#             try:
#                 value = getattr(provider, attr, None)
#                 if value:
#                     result.append(str(value))
#             except Exception:
#                 pass

#         return list(dict.fromkeys(result))

#     def _registry_model_provider_pairs(self):
#         pairs = []

#         # Current G4F ModelRegistry/__models__.
#         try:
#             models_module = __import__("g4f.models", fromlist=["__models__"])
#             registry = getattr(models_module, "__models__", {})
#             for model_name, entry in registry.items():
#                 try:
#                     _model, providers = entry
#                 except Exception:
#                     continue

#                 for provider in providers or []:
#                     if isinstance(provider, str):
#                         pairs.append((provider, model_name))
#                     else:
#                         pairs.append(
#                             (self._provider_name(provider), model_name)
#                         )
#         except Exception:
#             pass

#         return pairs

#     def _discover_candidates(self):
#         candidates = []

#         # 1. Explicit G4F model registry mappings.
#         candidates.extend(self._registry_model_provider_pairs())

#         # 2. Every provider and every model advertised by that provider.
#         for provider in self._provider_registry():
#             provider_name = self._provider_name(provider)
#             models = self._model_names_from_provider(provider)

#             # If a provider doesn't advertise a model, its default_model
#             # may still be usable.
#             for model_name in models:
#                 candidates.append((provider_name, model_name))

#         # 3. If G4F_MODEL is explicitly supplied, prioritize that model
#         # across every discovered provider. This still checks all providers.
#         forced_model = os.getenv("G4F_MODEL", "").strip()
#         if forced_model:
#             provider_names = [
#                 self._provider_name(p)
#                 for p in self._provider_registry()
#             ]
#             candidates = (
#                 [(p, forced_model) for p in provider_names]
#                 + candidates
#             )

#         # Remove impossible routing pseudo-providers.
#         blocked = {
#             "AnyProvider",
#             "G4FSpace",
#         }

#         cleaned = []
#         seen = set()

#         for provider_name, model_name in candidates:
#             provider_name = str(provider_name)
#             model_name = str(model_name)

#             if not provider_name or not model_name:
#                 continue
#             if provider_name in blocked:
#                 continue

#             key = (provider_name, model_name)
#             if key not in seen:
#                 seen.add(key)
#                 cleaned.append(key)

#         # Prefer commonly free/anonymous providers first, but do NOT remove
#         # anything. The user asked for exhaustive checking. Vision-capable
#         # providers are nudged slightly earlier too, since with use_vision
#         # enabled they're the ones that can actually act on what the page
#         # looks like rather than the text-only DOM dump.
#         preferred = {
#             "Pollinations": 0,
#             "Gemini": 1,
#             "GeminiPro": 2,
#             "DeepInfra": 3,
#             "HuggingSpace": 4,
#             "HuggingChat": 5,
#             "Qwen": 6,
#             "Together": 7,
#             "TeachAnything": 8,
#         }

#         def sort_key(pair):
#             provider_name, model_name = pair
#             vision_rank = 0 if provider_name in VISION_CAPABLE_PROVIDERS else 1
#             return (
#                 vision_rank,
#                 preferred.get(provider_name, 100),
#                 provider_name,
#                 model_name,
#             )

#         cleaned.sort(key=sort_key)

#         if self._max_candidates:
#             return cleaned[:self._max_candidates]

#         return cleaned

#     def _resolve_provider(self, provider_name):
#         try:
#             return getattr(self._g4f.Provider, provider_name)
#         except Exception as e:
#             raise RuntimeError(
#                 f"Provider '{provider_name}' is unavailable."
#             ) from e

#     def _request_with_provider(self, provider_name, model, messages):
#         provider = self._resolve_provider(provider_name)
#         client = self._Client(provider=provider)

#         kwargs = {
#             "model": model,
#             "messages": messages,
#             "stream": False,
#             "temperature": self.temperature,
#         }

#         try:
#             return client.chat.completions.create(**kwargs)
#         except TypeError:
#             kwargs.pop("temperature", None)
#             return client.chat.completions.create(**kwargs)

#     @staticmethod
#     def _append_schema_instruction(converted_messages, schema_instruction):
#         """
#         Append the JSON-schema instruction to a COPY of the last message
#         in an already-converted (plain dict) message list, mirroring the
#         original adapter's behavior. This never touches browser-use's own
#         message objects -- only our own throwaway dicts built fresh per
#         candidate by _convert_messages -- so nothing gets mutated in place
#         or accumulates across steps.
#         """
#         if not schema_instruction or not converted_messages:
#             return converted_messages

#         patched = list(converted_messages)
#         last = dict(patched[-1])
#         content = last.get("content", "")

#         if isinstance(content, list):
#             last["content"] = content + [
#                 {"type": "text", "text": schema_instruction}
#             ]
#         else:
#             last["content"] = str(content or "") + schema_instruction

#         patched[-1] = last
#         return patched

#     def _request_one(
#         self, index, provider_name, model, raw_messages, schema_instruction=None
#     ):
#         """
#         Execute exactly one provider/model request.

#         Each candidate gets its own G4F Client instance so the requests can
#         safely be executed in parallel threads.

#         If the provider is believed to support vision (see
#         VISION_CAPABLE_PROVIDERS) and the messages actually contain an
#         image, we first try a real multimodal call so the model can see
#         the screenshot browser-use attached. If that call fails for any
#         reason (provider rejects multimodal, malformed content, etc.), we
#         transparently retry the same candidate with a text-only rendering
#         instead of just giving up on it -- so a provider that turns out
#         not to support vision after all doesn't get dropped from the scan,
#         it just falls back to text like every other candidate.
#         """
#         key = (provider_name, model)
#         is_vision_candidate = provider_name in VISION_CAPABLE_PROVIDERS

#         attempts = []
#         if is_vision_candidate:
#             attempts.append((
#                 "vision",
#                 self._append_schema_instruction(
#                     self._convert_messages(raw_messages, multimodal=True),
#                     schema_instruction,
#                 ),
#             ))
#         attempts.append((
#             "text",
#             self._append_schema_instruction(
#                 self._convert_messages(raw_messages, multimodal=False),
#                 schema_instruction,
#             ),
#         ))

#         last_error = None

#         try:
#             for mode, messages in attempts:
#                 try:
#                     response = self._request_with_provider(
#                         provider_name,
#                         model,
#                         messages,
#                     )

#                     text = self._extract_g4f_text(response)

#                     if not text:
#                         raise RuntimeError("empty response")

#                     return {
#                         "ok": True,
#                         "provider": provider_name,
#                         "model": model,
#                         "response": response,
#                         "text": text,
#                         "error": None,
#                         "key": key,
#                         "used_vision": mode == "vision",
#                     }

#                 except Exception as e:
#                     last_error = f"{type(e).__name__}: {e}"
#                     # If the vision attempt failed, fall through to the
#                     # text-only attempt instead of failing this candidate.
#                     continue

#             return {
#                 "ok": False,
#                 "provider": provider_name,
#                 "model": model,
#                 "response": None,
#                 "text": "",
#                 "error": last_error,
#                 "key": key,
#                 "used_vision": False,
#             }

#         finally:
#             # Restores the original behavior: every candidate increments
#             # the progress counter exactly once, whether it ultimately
#             # succeeded or failed, so the live progress bar tracks real
#             # completions instead of jumping straight to 100% at the end.
#             self._completed_count += 1

#     async def _request_all_concurrently(self, messages, schema_instruction=None):
#         """
#         Launch EVERY discovered provider/model combination concurrently.

#         We do not wait for provider A before starting provider B.

#         The caller receives all completed responses so ainvoke() can choose
#         the first response that is actually valid for Browser Use's schema.

#         NOTE: self._tested is reset at the top of every call. Browser-use
#         invokes this adapter once per agent step, and each step needs its
#         own full scan of every discovered provider/model combination --
#         otherwise, once one step exhausts the candidate list, every later
#         step would immediately fail with "already tested" and the agent
#         could never recover from a bad pick.
#         """

#         self._tested = set()

#         candidates = [
#             (index, provider_name, model)
#             for index, (provider_name, model)
#             in enumerate(self._candidates, 1)
#             if (provider_name, model) not in self._tested
#         ]

#         if not candidates:
#             raise RuntimeError(
#                 "All discovered provider/model combinations have already "
#                 "been tested."
#             )

#         # Mark them before launching. This prevents duplicate launches if
#         # browser-use invokes the same LLM object again within this call.
#         for _, provider_name, model in candidates:
#             self._tested.add((provider_name, model))

#         self._completed_count = 0

#         tasks = [
#             asyncio.to_thread(
#                 self._request_one,
#                 index,
#                 provider_name,
#                 model,
#                 messages,
#                 schema_instruction,
#             )
#             for index, provider_name, model in candidates
#         ]

#         progress_task = asyncio.create_task(
#             self._report_progress(len(candidates))
#         )

#         # return_exceptions=True is important: one dead provider must never
#         # cancel the other provider/model requests.
#         results = await asyncio.gather(
#             *tasks,
#             return_exceptions=True,
#         )

#         self._completed_count = len(candidates)
#         await progress_task

#         normalized = []

#         for candidate, result in zip(candidates, results):
#             index, provider_name, model = candidate

#             if isinstance(result, Exception):
#                 normalized.append({
#                     "ok": False,
#                     "provider": provider_name,
#                     "model": model,
#                     "response": None,
#                     "text": "",
#                     "error": (
#                         f"{type(result).__name__}: {result}"
#                     ),
#                     "key": (provider_name, model),
#                     "used_vision": False,
#                 })
#             else:
#                 normalized.append(result)

#         success_count = sum(
#             1 for result in normalized if result["ok"]
#         )
#         vision_success_count = sum(
#             1 for result in normalized if result["ok"] and result.get("used_vision")
#         )

#         print(
#             f"  {success_count}/{len(normalized)} model sources responded "
#             f"({vision_success_count} with real vision input)."
#         )

#         return normalized

#     async def _report_progress(self, total):
#         """Live single-line progress bar shown while every candidate is
#         queried concurrently, replacing a per-candidate print log."""

#         if total <= 0:
#             return

#         frames = itertools.cycle(SPINNER_FRAMES)

#         while self._completed_count < total:
#             frame = next(frames)
#             filled = int(PROGRESS_BAR_LEN * self._completed_count / total)
#             bar = "#" * filled + "-" * (PROGRESS_BAR_LEN - filled)
#             pct = int(100 * self._completed_count / total)
#             sys.stdout.write(
#                 f"\r  {frame} Scanning models  [{bar}] "
#                 f"{self._completed_count:>4}/{total} ({pct:>3}%)  "
#             )
#             sys.stdout.flush()
#             await asyncio.sleep(0.08)

#         bar = "#" * PROGRESS_BAR_LEN
#         sys.stdout.write(
#             f"\r  * Scan complete   [{bar}] {total:>4}/{total} (100%)  \n"
#         )
#         sys.stdout.flush()

#     def _validate_and_repair_output(self, text, output_format):
#         """
#         Convert a raw G4F response into Browser Use's expected Pydantic
#         output. Returns the validated model or None.
#         """

#         data = self._extract_json(text)

#         if not isinstance(data, dict):
#             return None

#         try:
#             return output_format.model_validate(data)

#         except Exception:
#             action = data.get("action")

#             if not isinstance(action, list):
#                 return None

#             try:
#                 action_candidates = self._get_action_candidates(
#                     output_format
#                 )

#                 repaired_actions, changed = self._repair_action_list(
#                     action,
#                     action_candidates,
#                 )

#                 if not changed:
#                     return None

#                 data["action"] = repaired_actions

#                 return output_format.model_validate(data)

#             except Exception:
#                 return None

#     async def _request(self, messages, output_format=None, schema_instruction=None):
#         """
#         Concurrently query all discovered candidates and select the first
#         response that is usable.

#         If a Browser Use output schema is supplied, "usable" means the
#         response successfully parses AND validates against that schema.
#         This is stronger than merely checking that a provider returned text.

#         Candidates are evaluated in the adapter's canonical candidate order
#         (see _discover_candidates), NOT in whatever order they happened to
#         finish -- so this picks the first candidate that actually produces
#         a schema-valid, actionable response, rather than whichever provider
#         merely answered fastest. Vision-capable providers are sorted first,
#         so when a valid response exists from one of them it's preferred
#         over a text-only guess.
#         """

#         results = await self._request_all_concurrently(
#             messages, schema_instruction=schema_instruction
#         )

#         # Browser Use structured output:
#         # select the first provider/model whose response validates correctly.
#         if output_format is not None:
#             for result in results:
#                 if not result["ok"]:
#                     continue

#                 parsed = self._validate_and_repair_output(
#                     result["text"],
#                     output_format,
#                 )

#                 if parsed is not None:
#                     self._last_provider = result["provider"]
#                     self._last_model = result["model"]
#                     self._successful = result["key"]

#                     vision_note = (
#                         " (with vision)" if result.get("used_vision") else ""
#                     )
#                     print(
#                         f"  -> Using {result['provider']} / "
#                         f"{result['model']}{vision_note}"
#                     )

#                     return result, parsed

#             errors = [
#                 (
#                     f"{r['provider']}/{r['model']}: "
#                     f"{r['error']}"
#                 )
#                 for r in results
#                 if not r["ok"]
#             ]

#             raise RuntimeError(
#                 "All concurrent requests failed schema validation "
#                 "or failed to respond.\n"
#                 + "\n".join(f"  - {x}" for x in errors)
#             )

#         # Non-structured response: select first usable text.
#         for result in results:
#             if result["ok"] and result["text"]:
#                 self._last_provider = result["provider"]
#                 self._last_model = result["model"]
#                 self._successful = result["key"]

#                 vision_note = (
#                     " (with vision)" if result.get("used_vision") else ""
#                 )
#                 print(
#                     f"  -> Using {result['provider']} / {result['model']}{vision_note}"
#                 )

#                 return result, result["text"]

#         raise RuntimeError(
#             "All concurrent requests failed."
#         )

#     async def ainvoke(
#         self,
#         messages,
#         output_format=None,
#         request_type="browser_agent",
#         **kwargs: Any,
#     ):
#         # NOTE: we intentionally pass the raw browser-use message objects
#         # through to _request/_request_one, NOT a pre-flattened text
#         # version -- _request_one decides per-candidate whether to render
#         # them as multimodal or text-only. Flattening here (like the old
#         # implementation did) is what silently threw away every screenshot.
#         #
#         # The JSON-schema instruction (below) is applied later, per
#         # candidate, onto a fresh COPY of each candidate's own converted
#         # message list -- never onto these raw browser-use objects, which
#         # may be reused/logged elsewhere and must not be mutated.
#         raw_messages = list(messages)

#         schema_instruction = None
#         if output_format is not None:
#             schema = output_format.model_json_schema()
#             schema_instruction = (
#                 "\n\nIMPORTANT: Return ONLY valid JSON. "
#                 "Do not use markdown fences or explanatory text. "
#                 "The JSON MUST conform exactly to this schema:\n"
#                 + json.dumps(schema, ensure_ascii=False)
#             )

#         selected, parsed_result = await self._request(
#             raw_messages,
#             output_format=output_format,
#             schema_instruction=schema_instruction,
#         )

#         if output_format is None:
#             return ChatInvokeCompletion(
#                 completion=parsed_result,
#                 usage=None,
#             )

#         # parsed_result has already been validated against output_format
#         # by _request(), so Browser Use receives the selected model's
#         # structured response directly.
#         return ChatInvokeCompletion(
#             completion=parsed_result,
#             usage=None,
#         )

#     def _get_action_candidates(self, output_format):
#         try:
#             action_annotation = (
#                 output_format.model_fields["action"].annotation
#             )
#         except Exception:
#             return []

#         outer_args = get_args(action_annotation)
#         candidates = []

#         for arg in outer_args:
#             inner_args = get_args(arg)
#             candidates.extend(inner_args if inner_args else [arg])

#         return [
#             c for c in candidates
#             if hasattr(c, "model_fields")
#         ]

#     def _find_action_field(self, action_candidates, key):
#         for candidate in action_candidates:
#             field = candidate.model_fields.get(key)
#             if field is not None:
#                 return field
#         return None

#     def _repair_action_list(self, action_list, action_candidates):
#         repaired = []
#         changed = False

#         for item in action_list:
#             if not isinstance(item, dict) or len(item) != 1:
#                 repaired.append(item)
#                 continue

#             (key, value), = item.items()
#             field = self._find_action_field(action_candidates, key)

#             if field is None:
#                 repaired.append(item)
#                 continue

#             sub_model = field.annotation
#             origin = get_origin(sub_model)

#             if origin is not None:
#                 inner = [
#                     a for a in get_args(sub_model)
#                     if a is not type(None)
#                 ]
#                 if inner:
#                     sub_model = inner[0]

#             if not hasattr(sub_model, "model_fields"):
#                 repaired.append(item)
#                 continue

#             required_fields = [
#                 fname
#                 for fname, finfo in sub_model.model_fields.items()
#                 if finfo.is_required()
#             ]

#             if not isinstance(value, dict):
#                 if len(required_fields) == 1:
#                     repaired.append({
#                         key: {required_fields[0]: value}
#                     })
#                     changed = True
#                 else:
#                     repaired.append(item)
#                 continue

#             valid_keys = set(sub_model.model_fields.keys())

#             if set(value.keys()) <= valid_keys:
#                 repaired.append(item)
#                 continue

#             if len(required_fields) == 1 and len(value) == 1:
#                 ((_wrong_key, only_val),) = value.items()
#                 repaired.append({
#                     key: {required_fields[0]: only_val}
#                 })
#                 changed = True
#             else:
#                 repaired.append(item)

#         return repaired, changed


# # ==========================================================
# # LLM
# # ==========================================================

# llm = G4FExhaustiveBrowserUseLLM(
#     model=os.getenv("G4F_MODEL") or None,
#     temperature=0.2,
# )

# # ==========================================================
# # TERMINAL ACCESS
# #
# # Gives the agent a shell/terminal action it can call as a normal tool,
# # alongside its browser actions (click, scroll, select_dropdown, input,
# # extract, etc. -- all registered by default on Tools()/Controller()).
# # Every command runs with its working directory fixed to the folder this
# # script lives in.
# #
# # NOTE on scope: fixing cwd only sets the *starting* directory for the
# # command. A command that itself does `cd ..` or references an absolute
# # path elsewhere is not blocked -- there is no filesystem sandbox/chroot
# # here, just a scoped starting point. Only run this with tasks you trust.
# # ==========================================================

# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# def _build_tools():
#     """
#     Register a terminal-command action on a browser-use Tools/Controller
#     instance. This ADDS one action on top of the full default action set
#     (click, scroll, select_dropdown, dropdown_options, input, extract,
#     send_keys, upload_file, etc.) -- it never removes or replaces them.

#     Returns None (instead of raising) if the installed browser-use version
#     doesn't expose Tools/Controller/actions the way this code expects, so
#     the agent still runs in browser-only mode rather than crashing on
#     startup.
#     """

#     ActionResult = None
#     for path in (
#         "browser_use.agent.views",
#         "browser_use",
#     ):
#         try:
#             module = __import__(path, fromlist=["ActionResult"])
#             ActionResult = getattr(module, "ActionResult", None)
#             if ActionResult is not None:
#                 break
#         except Exception:
#             continue

#     try:
#         tools = Controller()

#         @tools.action(
#             "Run a shell/terminal command. It always starts in the "
#             f"agent's own working folder ({SCRIPT_DIR}). Use this for "
#             "file operations, running local scripts, checking installed "
#             "tools, or anything else that needs a real terminal instead "
#             "of a browser."
#         )
#         def run_terminal_command(command: str):
#             import subprocess

#             try:
#                 completed = subprocess.run(
#                     command,
#                     shell=True,
#                     cwd=SCRIPT_DIR,
#                     capture_output=True,
#                     text=True,
#                     timeout=120,
#                 )
#                 output = (
#                     (completed.stdout or "") + (completed.stderr or "")
#                 ).strip()
#                 if not output:
#                     output = (
#                         f"(command exited with code {completed.returncode}, "
#                         "no output)"
#                     )
#                 output = output[:4000]
#             except subprocess.TimeoutExpired:
#                 output = "Command timed out after 120 seconds."
#             except Exception as e:
#                 output = f"Command failed: {type(e).__name__}: {e}"

#             if ActionResult is not None:
#                 try:
#                     return ActionResult(
#                         extracted_content=output,
#                         include_in_memory=True,
#                     )
#                 except TypeError:
#                     return ActionResult(extracted_content=output)

#             return output

#         return tools

#     except Exception as e:
#         print(f"  Terminal-access tool unavailable: {e}")
#         return None


# # ==========================================================
# # PERSISTENCE GUIDANCE
# #
# # Left to itself the agent tends to take the easy way out: hit one
# # obstacle (a login wall, an ambiguous name) and immediately end the
# # task by asking the user a clarifying question -- even when it
# # already found the concrete answer (e.g. a real profile URL) and
# # just didn't report it. This nudges it to keep trying reasonable
# # alternate strategies and to only finish once it has something
# # concrete and verifiable, not before.
# #
# # It also spells out the default action set explicitly (click, scroll,
# # select_dropdown, send_keys, ...), since models -- especially small or
# # unreliable free ones being exhaustively scanned here -- sometimes
# # don't reliably infer the full action list on their own.
# # ==========================================================

# AGENT_PERSISTENCE_GUIDANCE = (
#     "Persistence and completion policy: "
#     "When the task requires finding specific, verifiable information "
#     "(such as a person's profile, a document, or a piece of data), do "
#     "not stop and ask the user a clarifying question while reasonable, "
#     "untried strategies remain. Before giving up, try alternate search "
#     "phrasings, common alternate spellings, other search engines, and "
#     "extracting URLs directly from search result links (e.g. via the "
#     "extract action, or by reading link hrefs from the page) instead "
#     "of only opening pages that require a login. "
#     "If you find candidate results, prefer extracting and reporting "
#     "the concrete details (such as the actual URL) over describing "
#     "them in vague prose. "
#     "You have real browser interaction actions available -- click, "
#     "input (typing into fields), scroll, select_dropdown, send_keys, "
#     "upload_file, and extract -- and should use them directly on the "
#     "actual page elements rather than describing what you would do. "
#     "If a click doesn't seem to land on the intended element, re-check "
#     "the current element index list before retrying rather than "
#     "repeating the same click. If a dropdown or select element is "
#     "involved, use select_dropdown / dropdown_options rather than "
#     "trying to type the value directly. "
#     "You also have a terminal-command action available, scoped to your "
#     "own working folder -- use it for local file work, running scripts, "
#     "or checking installed tools whenever that's a better fit than the "
#     "browser. "
#     "Only call `done` with success=true once you have concrete, "
#     "verifiable evidence for the answer. Only call `done` with "
#     "success=false after you have exhausted the reasonable strategies "
#     "available to you, and explain specifically what you tried and "
#     "why each attempt did not resolve the task."
# )


# def build_agent(task, tools=None):
#     """
#     Construct the browser-use Agent with persistence guidance, terminal
#     access, real vision (screenshots forwarded to vision-capable
#     providers -- see G4FExhaustiveBrowserUseLLM), and a higher failure
#     budget, falling back gracefully if the installed browser-use version
#     doesn't support one of these kwargs.
#     """

#     base_kwargs = dict(
#         task=task,
#         llm=llm,
#         use_vision=True,
#         max_actions_per_step=10,
#     )

#     # browser-use's current Agent parameter is `tools=`; `controller=` is
#     # kept as a backwards-compatible alias in the library. We pass `tools=`
#     # first and fall back to `controller=` for older installs.
#     tools_kwarg_variants = (
#         [dict(tools=tools), dict(controller=tools)]
#         if tools is not None
#         else [dict()]
#     )

#     optional_kwarg_sets = []
#     for tools_kwargs in tools_kwarg_variants:
#         optional_kwarg_sets.append(
#             dict(
#                 **tools_kwargs,
#                 extend_system_message=AGENT_PERSISTENCE_GUIDANCE,
#                 max_failures=8,
#             )
#         )
#         optional_kwarg_sets.append(
#             dict(**tools_kwargs, extend_system_message=AGENT_PERSISTENCE_GUIDANCE)
#         )
#         optional_kwarg_sets.append(dict(**tools_kwargs, max_failures=8))
#         optional_kwarg_sets.append(dict(**tools_kwargs))

#     # If the tools/controller kwarg itself isn't accepted by this
#     # browser-use version, fall back further to browser-only mode rather
#     # than failing to start the agent at all.
#     optional_kwarg_sets.extend([
#         dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE, max_failures=8),
#         dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE),
#         dict(max_failures=8),
#         dict(),
#     ])

#     last_error = None

#     for extra_kwargs in optional_kwarg_sets:
#         try:
#             agent = Agent(**base_kwargs, **extra_kwargs)

#             if extra_kwargs:
#                 print(f"  Agent options: {list(extra_kwargs)}")

#             return agent

#         except TypeError as e:
#             last_error = e
#             continue

#     raise last_error


# async def run_agent(agent):
#     """
#     Run the agent with a larger step budget when supported, falling
#     back to the default if this browser-use version doesn't accept
#     max_steps on run().
#     """

#     try:
#         return await agent.run(max_steps=50)
#     except TypeError:
#         return await agent.run()


# # ==========================================================
# # TASK INPUT
# # ==========================================================

# def get_ui_task():

#     task = os.getenv("AGENT_TASK", "").strip()

#     if task:
#         return task

#     try:
#         if not sys.stdin.isatty():
#             data = sys.stdin.read().strip()
#             if data:
#                 return data
#     except Exception:
#         pass

#     return ""


# # ==========================================================
# # MAIN
# #
# # Runs as a persistent loop: it never exits after a single task.
# # Once one task finishes (or fails), it asks for the next one. Type
# # 'exit' / 'quit', or press Ctrl+C, to actually stop the process.
# # ==========================================================

# async def main():

#     print_startup_banner(len(llm._candidates))
#     print(_boxed(["Terminal access folder:", SCRIPT_DIR[:BANNER_WIDTH - 6]]))

#     tools = _build_tools()

#     print(_boxed(["Persistent mode: running until you type 'exit'"]))

#     # Only the very first task may come from AGENT_TASK / piped stdin.
#     # Every task after that is asked for interactively -- otherwise a
#     # fixed AGENT_TASK env var or an exhausted stdin pipe would either
#     # loop forever on the same task or spin with nothing to do.
#     pending_task = get_ui_task()

#     while True:
#         if pending_task:
#             task = pending_task
#             pending_task = None
#         else:
#             try:
#                 task = input(
#                     "\nEnter the next task (or 'exit' to quit):\n> "
#                 ).strip()
#             except (EOFError, KeyboardInterrupt):
#                 print("\n\nShutting down.")
#                 break

#         if not task:
#             continue

#         if task.lower() in {"exit", "quit"}:
#             print("\nShutting down.")
#             break

#         print("\nTask received. Starting agent...\n")

#         try:
#             agent = build_agent(task, tools=tools)
#             result = await run_agent(agent)

#             print()
#             print(_boxed(["FINAL RESULT"]))
#             print(result)

#         except Exception as e:
#             print()
#             print(_boxed(["AGENT ERROR", "", repr(e)[:BANNER_WIDTH - 6]]))
#             print("  Continuing -- ready for the next task.")


# if __name__ == "__main__":
#     asyncio.run(main())





import asyncio
import itertools
import json
import os
import re
import sys
from typing import Any, get_args, get_origin


from browser_use import Agent

try:
    from browser_use import Tools as Controller
except ImportError:
    from browser_use import Controller

from browser_use.llm.views import ChatInvokeCompletion


# ==========================================================
# NIZAM AGENT 1 — EXHAUSTIVE MULTI-PROVIDER LLM ADAPTER
# ==========================================================

BANNER_WIDTH = 64
SPINNER_FRAMES = "|/-\\"
PROGRESS_BAR_LEN = 30

# Providers known to accept OpenAI-style multimodal ("image_url") content
# blocks in their chat messages, at all, for at least some of their models.
# NOTE: this alone is NOT enough to trust vision -- see
# VISION_CAPABLE_MODEL_PATTERNS below. Several of these providers (e.g.
# HuggingSpace, DeepInfra, Together) proxy dozens of unrelated models, most
# of which are text-only, and silently ignore image content instead of
# erroring on it. A provider match without a model match is NOT treated as
# a real vision candidate.
VISION_CAPABLE_PROVIDERS = {
    "Gemini",
    "GeminiPro",
    "HuggingSpace",
    "HuggingChat",
    "PollinationsAI",
    "Pollinations",
    "OpenaiChat",
    "Blackbox",
    "Qwen",
    "DeepInfra",
    "Together",
    "CopilotAccount",
    "MetaAI",
}

# Substrings that identify a MODEL as actually vision-capable, regardless
# of which provider serves it. A (provider, model) pair only gets treated
# as a real vision candidate if the provider is in VISION_CAPABLE_PROVIDERS
# AND the model name matches one of these patterns. This is what stops a
# text-only model like Cohere's "command-a" (served incidentally via the
# HuggingSpace router) from being falsely trusted with a screenshot it
# can't actually see.
VISION_CAPABLE_MODEL_PATTERNS = (
    "vision",
    "vl",              # qwen-vl, cogvlm, etc.
    "llava",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4.1",
    "gpt-5",
    "o3",
    "o4",
    "gemini",
    "claude-3",
    "claude-4",
    "claude-opus",
    "claude-sonnet",
    "claude-haiku",
    "internvl",
    "idefics",
    "pixtral",
    "phi-3-vision",
    "phi-4-multimodal",
    "qwen2-vl",
    "qwen2.5-vl",
    "moondream",
    "florence",
    "cogvlm",
    "yi-vl",
    "grok",
    "multimodal",
)


def _model_is_vision_capable(model_name):
    lowered = model_name.lower()
    return any(pattern in lowered for pattern in VISION_CAPABLE_MODEL_PATTERNS)


def _boxed(lines, width=BANNER_WIDTH):
    """Render centered lines inside a plain-ASCII box (font/encoding safe)."""
    top = "+" + "-" * (width - 2) + "+"
    out = [top]
    for line in lines:
        inner = width - 2
        pad_total = max(inner - len(line), 0)
        left = pad_total // 2
        right = pad_total - left
        out.append("|" + " " * left + line + " " * right + "|")
    out.append(top)
    return "\n".join(out)


def print_startup_banner(total_candidates):
    banner = [
        "",
        "N I Z A M   A G E N T   1",
        "",
        "Exhaustive Multi-Provider Browser Agent",
        f"{total_candidates} model sources loaded",
        "",
    ]
    print()
    print(_boxed(banner))
    print()

class G4FExhaustiveBrowserUseLLM:
    """
    Browser-use LLM adapter that discovers G4F's installed provider/model
    registry at runtime and tests provider/model combinations until one
    actually answers.

    It intentionally does NOT use AnyProvider or model-router.

    Discovery sources:
      1. G4F ModelRegistry / __models__ when available.
      2. Every provider exposed by g4f.Provider.__providers__.
      3. Provider-declared model lists/default_model when available.

    Providers/models that require authentication can be discovered and
    tested, but failures are skipped. This means the agent does not stop
    simply because one provider is unavailable.

    Vision: browser-use sends multimodal messages (a text part plus one or
    more image_url parts, e.g. screenshots) whenever the Agent is built
    with use_vision=True. This adapter now forwards those image blocks
    as real OpenAI-style multimodal content to providers believed to
    support vision (see VISION_CAPABLE_PROVIDERS), instead of silently
    discarding them. For every other provider -- and as an automatic
    fallback if a multimodal call fails -- it falls back to a text-only
    call with a short marker noting an image was omitted, so the scan
    stays exhaustive and never hard-fails just because one candidate
    can't see images.
    """

    provider = "Nizam Agent 1"

    def __init__(self, model=None, temperature=0.2):
        try:
            import g4f
            from g4f.client import Client
        except Exception as e:
            raise RuntimeError(
                "A required backend package is missing or outdated. "
                "Install/update it with: pip install -U g4f"
            ) from e

        self._g4f = g4f
        self._Client = Client
        self.temperature = temperature
        self.model = model or os.getenv("G4F_MODEL", "").strip() or "auto-discovery"
        self._last_provider = None
        self._last_model = None
        self._tested = set()
        self._completed_count = 0
        self._successful = None

        # A true exhaustive scan can be very large. By default we test every
        # discovered pair. Set G4F_MAX_CANDIDATES only if you intentionally
        # want a cap.
        cap = os.getenv("G4F_MAX_CANDIDATES", "").strip()
        self._max_candidates = int(cap) if cap.isdigit() and int(cap) > 0 else None

        self._candidates = self._discover_candidates()

        if not self._candidates:
            raise RuntimeError(
                "No usable model sources were discovered."
            )

    @property
    def model_name(self):
        return self._last_model or self.model

    @property
    def model_provider(self):
        if self._last_provider and self._last_model:
            return f"{self._last_provider} / {self._last_model}"
        return "Nizam Agent 1 / auto-discovery"

    @staticmethod
    def _content_to_text(content):
        """Text-only rendering of a message's content (used for the
        text-only fallback path, and for providers we don't believe
        support vision)."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type in ("image_url", "image"):
                        parts.append("[image omitted - provider is text-only]")
                        continue
                    value = item.get("text")
                    if value:
                        parts.append(str(value))
                else:
                    value = getattr(item, "text", None)
                    if value:
                        parts.append(str(value))
                    else:
                        image_val = getattr(item, "image_url", None) or getattr(
                            item, "image", None
                        )
                        if image_val is not None:
                            parts.append(
                                "[image omitted - provider is text-only]"
                            )
                            continue
                        value = getattr(item, "value", None)
                        if value:
                            parts.append(str(value))
            return "\n".join(parts)
        return str(content)

    @staticmethod
    def _extract_image_url(item):
        """Best-effort extraction of a usable image URL/data-URI from a
        single content block, regardless of whether it's a dict or an
        object (browser-use's ContentPartImageParam or similar)."""
        if isinstance(item, dict):
            image_url = item.get("image_url")
            if isinstance(image_url, dict):
                return image_url.get("url")
            if isinstance(image_url, str):
                return image_url
            image = item.get("image")
            if isinstance(image, str):
                return image
            return None

        image_url = getattr(item, "image_url", None)
        if image_url is not None:
            url = getattr(image_url, "url", None)
            if url:
                return url
            if isinstance(image_url, str):
                return image_url

        image = getattr(item, "image", None)
        if isinstance(image, str):
            return image

        return None

    @classmethod
    def _content_to_multimodal(cls, content):
        """
        Render a message's content as OpenAI-style multimodal content
        blocks (list of {"type": "text"/"image_url", ...}) so a
        vision-capable provider actually receives the screenshot,
        instead of only the text browser-use attached alongside it.

        Returns a plain string if there are no image parts (nothing
        multimodal to send), or a list of content blocks if there is
        at least one image.
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)

        blocks = []
        has_image = False

        for item in content:
            if isinstance(item, str):
                if item:
                    blocks.append({"type": "text", "text": item})
                continue

            image_url = cls._extract_image_url(item)
            if image_url:
                has_image = True
                blocks.append(
                    {"type": "image_url", "image_url": {"url": image_url}}
                )
                continue

            text_val = None
            if isinstance(item, dict):
                text_val = item.get("text")
            else:
                text_val = getattr(item, "text", None)

            if text_val:
                blocks.append({"type": "text", "text": str(text_val)})

        if not has_image:
            # Nothing visual in this message -- a plain string is simpler
            # and works with every provider, vision-capable or not.
            return "\n".join(b["text"] for b in blocks if b.get("type") == "text")

        return blocks

    def _convert_messages(self, messages, multimodal=False):
        """
        Convert browser-use's internal message objects into plain
        OpenAI-style dicts.

        multimodal=True preserves image_url content blocks (for
        providers we're sending real vision to); multimodal=False
        collapses everything to text (safe default / fallback path).
        """
        converted = []
        for message in messages:
            message_type = type(message).__name__
            raw_content = getattr(message, "content", "")

            if multimodal:
                content = self._content_to_multimodal(raw_content)
            else:
                content = self._content_to_text(raw_content)

            if message_type == "SystemMessage":
                role = "system"
            elif message_type == "UserMessage":
                role = "user"
            elif message_type == "AssistantMessage":
                role = "assistant"
            else:
                role = getattr(message, "role", None) or "user"

            converted.append({"role": role, "content": content})
        return converted

    @staticmethod
    def _extract_json(text):
        if not text:
            return None

        text = text.strip()
        text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        try:
            return json.loads(text)
        except Exception:
            pass

        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(text[index:])
                return obj
            except Exception:
                continue

        return None

    @staticmethod
    def _extract_g4f_text(response):
        try:
            choices = getattr(response, "choices", None)
            if choices:
                message = getattr(choices[0], "message", None)
                content = getattr(message, "content", None)
                if content:
                    return str(content).strip()
        except Exception:
            pass

        if isinstance(response, dict):
            try:
                choices = response.get("choices") or []
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content")
                    if content:
                        return str(content).strip()
            except Exception:
                pass

        return ""

    @staticmethod
    def _provider_name(provider):
        return (
            getattr(provider, "label", None)
            or getattr(provider, "__name__", None)
            or str(provider)
        )

    def _provider_registry(self):
        providers = []

        try:
            registry = getattr(self._g4f.Provider, "__providers__", None)
            if registry:
                providers.extend(registry)
        except Exception:
            pass

        try:
            names = getattr(self._g4f.Provider, "__all__", [])
            for name in names:
                if name in {
                    "BaseProvider", "ProviderType", "RetryProvider",
                    "IterListProvider", "RotatedProvider",
                    "AsyncProvider", "AsyncGeneratorProvider",
                    "CreateImagesProvider", "ProviderUtils", "__providers__",
                    "__map__",
                }:
                    continue
                try:
                    provider = getattr(self._g4f.Provider, name)
                    if provider not in providers:
                        providers.append(provider)
                except Exception:
                    continue

        except Exception:
            pass

        return providers

    @staticmethod
    def _model_names_from_provider(provider):
        result = []

        for attr in ("models", "model_names"):
            try:
                values = getattr(provider, attr, None)
                if isinstance(values, str):
                    values = [values]
                if values:
                    result.extend(str(x) for x in values if x)
            except Exception:
                pass

        for attr in ("default_model", "default_vision_model"):
            try:
                value = getattr(provider, attr, None)
                if value:
                    result.append(str(value))
            except Exception:
                pass

        return list(dict.fromkeys(result))

    def _registry_model_provider_pairs(self):
        pairs = []

        # Current G4F ModelRegistry/__models__.
        try:
            models_module = __import__("g4f.models", fromlist=["__models__"])
            registry = getattr(models_module, "__models__", {})
            for model_name, entry in registry.items():
                try:
                    _model, providers = entry
                except Exception:
                    continue

                for provider in providers or []:
                    if isinstance(provider, str):
                        pairs.append((provider, model_name))
                    else:
                        pairs.append(
                            (self._provider_name(provider), model_name)
                        )
        except Exception:
            pass

        return pairs

    def _discover_candidates(self):
        candidates = []

        # 1. Explicit G4F model registry mappings.
        candidates.extend(self._registry_model_provider_pairs())

        # 2. Every provider and every model advertised by that provider.
        for provider in self._provider_registry():
            provider_name = self._provider_name(provider)
            models = self._model_names_from_provider(provider)

            # If a provider doesn't advertise a model, its default_model
            # may still be usable.
            for model_name in models:
                candidates.append((provider_name, model_name))

        # 3. If G4F_MODEL is explicitly supplied, prioritize that model
        # across every discovered provider. This still checks all providers.
        forced_model = os.getenv("G4F_MODEL", "").strip()
        if forced_model:
            provider_names = [
                self._provider_name(p)
                for p in self._provider_registry()
            ]
            candidates = (
                [(p, forced_model) for p in provider_names]
                + candidates
            )

        # Remove impossible routing pseudo-providers.
        blocked = {
            "AnyProvider",
            "G4FSpace",
        }

        cleaned = []
        seen = set()

        for provider_name, model_name in candidates:
            provider_name = str(provider_name)
            model_name = str(model_name)

            if not provider_name or not model_name:
                continue
            if provider_name in blocked:
                continue

            key = (provider_name, model_name)
            if key not in seen:
                seen.add(key)
                cleaned.append(key)

        # Prefer commonly free/anonymous providers first, but do NOT remove
        # anything. The user asked for exhaustive checking. Vision-capable
        # providers are nudged slightly earlier too, since with use_vision
        # enabled they're the ones that can actually act on what the page
        # looks like rather than the text-only DOM dump.
        preferred = {
            "Pollinations": 0,
            "Gemini": 1,
            "GeminiPro": 2,
            "DeepInfra": 3,
            "HuggingSpace": 4,
            "HuggingChat": 5,
            "Qwen": 6,
            "Together": 7,
            "TeachAnything": 8,
        }

        def sort_key(pair):
            provider_name, model_name = pair
            vision_rank = (
                0
                if provider_name in VISION_CAPABLE_PROVIDERS
                and _model_is_vision_capable(model_name)
                else 1
            )
            return (
                vision_rank,
                preferred.get(provider_name, 100),
                provider_name,
                model_name,
            )

        cleaned.sort(key=sort_key)

        if self._max_candidates:
            return cleaned[:self._max_candidates]

        return cleaned

    def _resolve_provider(self, provider_name):
        try:
            return getattr(self._g4f.Provider, provider_name)
        except Exception as e:
            raise RuntimeError(
                f"Provider '{provider_name}' is unavailable."
            ) from e

    def _request_with_provider(self, provider_name, model, messages):
        provider = self._resolve_provider(provider_name)
        client = self._Client(provider=provider)

        kwargs = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": self.temperature,
        }

        try:
            return client.chat.completions.create(**kwargs)
        except TypeError:
            kwargs.pop("temperature", None)
            return client.chat.completions.create(**kwargs)

    @staticmethod
    def _append_schema_instruction(converted_messages, schema_instruction):
        """
        Append the JSON-schema instruction to a COPY of the last message
        in an already-converted (plain dict) message list, mirroring the
        original adapter's behavior. This never touches browser-use's own
        message objects -- only our own throwaway dicts built fresh per
        candidate by _convert_messages -- so nothing gets mutated in place
        or accumulates across steps.
        """
        if not schema_instruction or not converted_messages:
            return converted_messages

        patched = list(converted_messages)
        last = dict(patched[-1])
        content = last.get("content", "")

        if isinstance(content, list):
            last["content"] = content + [
                {"type": "text", "text": schema_instruction}
            ]
        else:
            last["content"] = str(content or "") + schema_instruction

        patched[-1] = last
        return patched

    def _request_one(
        self, index, provider_name, model, raw_messages, schema_instruction=None
    ):
        """
        Execute exactly one provider/model request.

        Each candidate gets its own G4F Client instance so the requests can
        safely be executed in parallel threads.

        If the provider is believed to support vision (see
        VISION_CAPABLE_PROVIDERS) and the messages actually contain an
        image, we first try a real multimodal call so the model can see
        the screenshot browser-use attached. If that call fails for any
        reason (provider rejects multimodal, malformed content, etc.), we
        transparently retry the same candidate with a text-only rendering
        instead of just giving up on it -- so a provider that turns out
        not to support vision after all doesn't get dropped from the scan,
        it just falls back to text like every other candidate.
        """
        key = (provider_name, model)
        is_vision_candidate = (
            provider_name in VISION_CAPABLE_PROVIDERS
            and _model_is_vision_capable(model)
        )

        attempts = []
        if is_vision_candidate:
            attempts.append((
                "vision",
                self._append_schema_instruction(
                    self._convert_messages(raw_messages, multimodal=True),
                    schema_instruction,
                ),
            ))
        attempts.append((
            "text",
            self._append_schema_instruction(
                self._convert_messages(raw_messages, multimodal=False),
                schema_instruction,
            ),
        ))

        last_error = None

        try:
            for mode, messages in attempts:
                try:
                    response = self._request_with_provider(
                        provider_name,
                        model,
                        messages,
                    )

                    text = self._extract_g4f_text(response)

                    if not text:
                        raise RuntimeError("empty response")

                    return {
                        "ok": True,
                        "provider": provider_name,
                        "model": model,
                        "response": response,
                        "text": text,
                        "error": None,
                        "key": key,
                        "used_vision": mode == "vision",
                    }

                except Exception as e:
                    last_error = f"{type(e).__name__}: {e}"
                    # If the vision attempt failed, fall through to the
                    # text-only attempt instead of failing this candidate.
                    continue

            return {
                "ok": False,
                "provider": provider_name,
                "model": model,
                "response": None,
                "text": "",
                "error": last_error,
                "key": key,
                "used_vision": False,
            }

        finally:
            # Restores the original behavior: every candidate increments
            # the progress counter exactly once, whether it ultimately
            # succeeded or failed, so the live progress bar tracks real
            # completions instead of jumping straight to 100% at the end.
            self._completed_count += 1

    async def _request_all_concurrently(self, messages, schema_instruction=None):
        """
        Launch EVERY discovered provider/model combination concurrently.

        We do not wait for provider A before starting provider B.

        The caller receives all completed responses so ainvoke() can choose
        the first response that is actually valid for Browser Use's schema.

        NOTE: self._tested is reset at the top of every call. Browser-use
        invokes this adapter once per agent step, and each step needs its
        own full scan of every discovered provider/model combination --
        otherwise, once one step exhausts the candidate list, every later
        step would immediately fail with "already tested" and the agent
        could never recover from a bad pick.
        """

        self._tested = set()

        candidates = [
            (index, provider_name, model)
            for index, (provider_name, model)
            in enumerate(self._candidates, 1)
            if (provider_name, model) not in self._tested
        ]

        if not candidates:
            raise RuntimeError(
                "All discovered provider/model combinations have already "
                "been tested."
            )

        # Mark them before launching. This prevents duplicate launches if
        # browser-use invokes the same LLM object again within this call.
        for _, provider_name, model in candidates:
            self._tested.add((provider_name, model))

        self._completed_count = 0

        tasks = [
            asyncio.to_thread(
                self._request_one,
                index,
                provider_name,
                model,
                messages,
                schema_instruction,
            )
            for index, provider_name, model in candidates
        ]

        progress_task = asyncio.create_task(
            self._report_progress(len(candidates))
        )

        # return_exceptions=True is important: one dead provider must never
        # cancel the other provider/model requests.
        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        self._completed_count = len(candidates)
        await progress_task

        normalized = []

        for candidate, result in zip(candidates, results):
            index, provider_name, model = candidate

            if isinstance(result, Exception):
                normalized.append({
                    "ok": False,
                    "provider": provider_name,
                    "model": model,
                    "response": None,
                    "text": "",
                    "error": (
                        f"{type(result).__name__}: {result}"
                    ),
                    "key": (provider_name, model),
                    "used_vision": False,
                })
            else:
                normalized.append(result)

        success_count = sum(
            1 for result in normalized if result["ok"]
        )
        vision_success_count = sum(
            1 for result in normalized if result["ok"] and result.get("used_vision")
        )

        print(
            f"  {success_count}/{len(normalized)} model sources responded "
            f"({vision_success_count} with real vision input)."
        )

        return normalized

    async def _report_progress(self, total):
        """Live single-line progress bar shown while every candidate is
        queried concurrently, replacing a per-candidate print log."""

        if total <= 0:
            return

        frames = itertools.cycle(SPINNER_FRAMES)

        while self._completed_count < total:
            frame = next(frames)
            filled = int(PROGRESS_BAR_LEN * self._completed_count / total)
            bar = "#" * filled + "-" * (PROGRESS_BAR_LEN - filled)
            pct = int(100 * self._completed_count / total)
            sys.stdout.write(
                f"\r  {frame} Scanning models  [{bar}] "
                f"{self._completed_count:>4}/{total} ({pct:>3}%)  "
            )
            sys.stdout.flush()
            await asyncio.sleep(0.08)

        bar = "#" * PROGRESS_BAR_LEN
        sys.stdout.write(
            f"\r  * Scan complete   [{bar}] {total:>4}/{total} (100%)  \n"
        )
        sys.stdout.flush()

    def _validate_and_repair_output(self, text, output_format):
        """
        Convert a raw G4F response into Browser Use's expected Pydantic
        output. Returns the validated model or None.
        """

        data = self._extract_json(text)

        if not isinstance(data, dict):
            return None

        try:
            return output_format.model_validate(data)

        except Exception:
            action = data.get("action")

            if not isinstance(action, list):
                return None

            try:
                action_candidates = self._get_action_candidates(
                    output_format
                )

                repaired_actions, changed = self._repair_action_list(
                    action,
                    action_candidates,
                )

                if not changed:
                    return None

                data["action"] = repaired_actions

                return output_format.model_validate(data)

            except Exception:
                return None

    async def _request(self, messages, output_format=None, schema_instruction=None):
        """
        Concurrently query all discovered candidates and select the first
        response that is usable.

        If a Browser Use output schema is supplied, "usable" means the
        response successfully parses AND validates against that schema.
        This is stronger than merely checking that a provider returned text.

        Candidates are evaluated in the adapter's canonical candidate order
        (see _discover_candidates), NOT in whatever order they happened to
        finish -- so this picks the first candidate that actually produces
        a schema-valid, actionable response, rather than whichever provider
        merely answered fastest. Vision-capable providers are sorted first,
        so when a valid response exists from one of them it's preferred
        over a text-only guess.
        """

        results = await self._request_all_concurrently(
            messages, schema_instruction=schema_instruction
        )

        # Browser Use structured output:
        # select the first provider/model whose response validates correctly.
        if output_format is not None:
            for result in results:
                if not result["ok"]:
                    continue

                parsed = self._validate_and_repair_output(
                    result["text"],
                    output_format,
                )

                if parsed is not None:
                    self._last_provider = result["provider"]
                    self._last_model = result["model"]
                    self._successful = result["key"]

                    vision_note = (
                        " (with vision)" if result.get("used_vision") else ""
                    )
                    print(
                        f"  -> Using {result['provider']} / "
                        f"{result['model']}{vision_note}"
                    )

                    return result, parsed

            errors = [
                (
                    f"{r['provider']}/{r['model']}: "
                    f"{r['error']}"
                )
                for r in results
                if not r["ok"]
            ]

            raise RuntimeError(
                "All concurrent requests failed schema validation "
                "or failed to respond.\n"
                + "\n".join(f"  - {x}" for x in errors)
            )

        # Non-structured response: select first usable text.
        for result in results:
            if result["ok"] and result["text"]:
                self._last_provider = result["provider"]
                self._last_model = result["model"]
                self._successful = result["key"]

                vision_note = (
                    " (with vision)" if result.get("used_vision") else ""
                )
                print(
                    f"  -> Using {result['provider']} / {result['model']}{vision_note}"
                )

                return result, result["text"]

        raise RuntimeError(
            "All concurrent requests failed."
        )

    async def ainvoke(
        self,
        messages,
        output_format=None,
        request_type="browser_agent",
        **kwargs: Any,
    ):
        # NOTE: we intentionally pass the raw browser-use message objects
        # through to _request/_request_one, NOT a pre-flattened text
        # version -- _request_one decides per-candidate whether to render
        # them as multimodal or text-only. Flattening here (like the old
        # implementation did) is what silently threw away every screenshot.
        #
        # The JSON-schema instruction (below) is applied later, per
        # candidate, onto a fresh COPY of each candidate's own converted
        # message list -- never onto these raw browser-use objects, which
        # may be reused/logged elsewhere and must not be mutated.
        raw_messages = list(messages)

        schema_instruction = None
        if output_format is not None:
            schema = output_format.model_json_schema()
            schema_instruction = (
                "\n\nIMPORTANT: Return ONLY valid JSON. "
                "Do not use markdown fences or explanatory text. "
                "The JSON MUST conform exactly to this schema:\n"
                + json.dumps(schema, ensure_ascii=False)
            )

        selected, parsed_result = await self._request(
            raw_messages,
            output_format=output_format,
            schema_instruction=schema_instruction,
        )

        if output_format is None:
            return ChatInvokeCompletion(
                completion=parsed_result,
                usage=None,
            )

        # parsed_result has already been validated against output_format
        # by _request(), so Browser Use receives the selected model's
        # structured response directly.
        return ChatInvokeCompletion(
            completion=parsed_result,
            usage=None,
        )

    def _get_action_candidates(self, output_format):
        try:
            action_annotation = (
                output_format.model_fields["action"].annotation
            )
        except Exception:
            return []

        outer_args = get_args(action_annotation)
        candidates = []

        for arg in outer_args:
            inner_args = get_args(arg)
            candidates.extend(inner_args if inner_args else [arg])

        return [
            c for c in candidates
            if hasattr(c, "model_fields")
        ]

    def _find_action_field(self, action_candidates, key):
        for candidate in action_candidates:
            field = candidate.model_fields.get(key)
            if field is not None:
                return field
        return None

    def _repair_action_list(self, action_list, action_candidates):
        repaired = []
        changed = False

        for item in action_list:
            if not isinstance(item, dict) or len(item) != 1:
                repaired.append(item)
                continue

            (key, value), = item.items()
            field = self._find_action_field(action_candidates, key)

            if field is None:
                repaired.append(item)
                continue

            sub_model = field.annotation
            origin = get_origin(sub_model)

            if origin is not None:
                inner = [
                    a for a in get_args(sub_model)
                    if a is not type(None)
                ]
                if inner:
                    sub_model = inner[0]

            if not hasattr(sub_model, "model_fields"):
                repaired.append(item)
                continue

            required_fields = [
                fname
                for fname, finfo in sub_model.model_fields.items()
                if finfo.is_required()
            ]

            if not isinstance(value, dict):
                if len(required_fields) == 1:
                    repaired.append({
                        key: {required_fields[0]: value}
                    })
                    changed = True
                else:
                    repaired.append(item)
                continue

            valid_keys = set(sub_model.model_fields.keys())

            if set(value.keys()) <= valid_keys:
                repaired.append(item)
                continue

            if len(required_fields) == 1 and len(value) == 1:
                ((_wrong_key, only_val),) = value.items()
                repaired.append({
                    key: {required_fields[0]: only_val}
                })
                changed = True
            else:
                repaired.append(item)

        return repaired, changed


# ==========================================================
# LLM
# ==========================================================

llm = G4FExhaustiveBrowserUseLLM(
    model=os.getenv("G4F_MODEL") or None,
    temperature=0.2,
)

# ==========================================================
# TERMINAL ACCESS
#
# Gives the agent a shell/terminal action it can call as a normal tool,
# alongside its browser actions (click, scroll, select_dropdown, input,
# extract, etc. -- all registered by default on Tools()/Controller()).
# Every command runs with its working directory fixed to the folder this
# script lives in.
#
# NOTE on scope: fixing cwd only sets the *starting* directory for the
# command. A command that itself does `cd ..` or references an absolute
# path elsewhere is not blocked -- there is no filesystem sandbox/chroot
# here, just a scoped starting point. Only run this with tasks you trust.
# ==========================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _build_tools():
    """
    Register a terminal-command action on a browser-use Tools/Controller
    instance. This ADDS one action on top of the full default action set
    (click, scroll, select_dropdown, dropdown_options, input, extract,
    send_keys, upload_file, etc.) -- it never removes or replaces them.

    Returns None (instead of raising) if the installed browser-use version
    doesn't expose Tools/Controller/actions the way this code expects, so
    the agent still runs in browser-only mode rather than crashing on
    startup.
    """

    ActionResult = None
    for path in (
        "browser_use.agent.views",
        "browser_use",
    ):
        try:
            module = __import__(path, fromlist=["ActionResult"])
            ActionResult = getattr(module, "ActionResult", None)
            if ActionResult is not None:
                break
        except Exception:
            continue

    try:
        tools = Controller()

        @tools.action(
            "Run a shell/terminal command. It always starts in the "
            f"agent's own working folder ({SCRIPT_DIR}). Use this for "
            "file operations, running local scripts, checking installed "
            "tools, or anything else that needs a real terminal instead "
            "of a browser."
        )
        def run_terminal_command(command: str):
            import subprocess

            try:
                completed = subprocess.run(
                    command,
                    shell=True,
                    cwd=SCRIPT_DIR,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = (
                    (completed.stdout or "") + (completed.stderr or "")
                ).strip()
                if not output:
                    output = (
                        f"(command exited with code {completed.returncode}, "
                        "no output)"
                    )
                output = output[:4000]
            except subprocess.TimeoutExpired:
                output = "Command timed out after 120 seconds."
            except Exception as e:
                output = f"Command failed: {type(e).__name__}: {e}"

            if ActionResult is not None:
                try:
                    return ActionResult(
                        extracted_content=output,
                        include_in_memory=True,
                    )
                except TypeError:
                    return ActionResult(extracted_content=output)

            return output

        return tools

    except Exception as e:
        print(f"  Terminal-access tool unavailable: {e}")
        return None


# ==========================================================
# PERSISTENCE GUIDANCE
#
# Left to itself the agent tends to take the easy way out: hit one
# obstacle (a login wall, an ambiguous name) and immediately end the
# task by asking the user a clarifying question -- even when it
# already found the concrete answer (e.g. a real profile URL) and
# just didn't report it. This nudges it to keep trying reasonable
# alternate strategies and to only finish once it has something
# concrete and verifiable, not before.
#
# It also spells out the default action set explicitly (click, scroll,
# select_dropdown, send_keys, ...), since models -- especially small or
# unreliable free ones being exhaustively scanned here -- sometimes
# don't reliably infer the full action list on their own.
# ==========================================================

AGENT_PERSISTENCE_GUIDANCE = (
    "Persistence and completion policy: "
    "When the task requires finding specific, verifiable information "
    "(such as a person's profile, a document, or a piece of data), do "
    "not stop and ask the user a clarifying question while reasonable, "
    "untried strategies remain. Before giving up, try alternate search "
    "phrasings, common alternate spellings, other search engines, and "
    "extracting URLs directly from search result links (e.g. via the "
    "extract action, or by reading link hrefs from the page) instead "
    "of only opening pages that require a login. "
    "If you find candidate results, prefer extracting and reporting "
    "the concrete details (such as the actual URL) over describing "
    "them in vague prose. "
    "You have real browser interaction actions available -- click, "
    "input (typing into fields), scroll, select_dropdown, send_keys, "
    "upload_file, and extract -- and should use them directly on the "
    "actual page elements rather than describing what you would do. "
    "If a click doesn't seem to land on the intended element, re-check "
    "the current element index list before retrying rather than "
    "repeating the same click. If a dropdown or select element is "
    "involved, use select_dropdown / dropdown_options rather than "
    "trying to type the value directly. "
    "You also have a terminal-command action available, scoped to your "
    "own working folder -- use it for local file work, running scripts, "
    "or checking installed tools whenever that's a better fit than the "
    "browser. "
    "Only call `done` with success=true once you have concrete, "
    "verifiable evidence for the answer. Only call `done` with "
    "success=false after you have exhausted the reasonable strategies "
    "available to you, and explain specifically what you tried and "
    "why each attempt did not resolve the task."
)


def build_agent(task, tools=None):
    """
    Construct the browser-use Agent with persistence guidance, terminal
    access, real vision (screenshots forwarded to vision-capable
    providers -- see G4FExhaustiveBrowserUseLLM), and a higher failure
    budget, falling back gracefully if the installed browser-use version
    doesn't support one of these kwargs.
    """

    base_kwargs = dict(
        task=task,
        llm=llm,
        use_vision=True,
        max_actions_per_step=10,
    )

    # browser-use's current Agent parameter is `tools=`; `controller=` is
    # kept as a backwards-compatible alias in the library. We pass `tools=`
    # first and fall back to `controller=` for older installs.
    tools_kwarg_variants = (
        [dict(tools=tools), dict(controller=tools)]
        if tools is not None
        else [dict()]
    )

    optional_kwarg_sets = []
    for tools_kwargs in tools_kwarg_variants:
        optional_kwarg_sets.append(
            dict(
                **tools_kwargs,
                extend_system_message=AGENT_PERSISTENCE_GUIDANCE,
                max_failures=8,
            )
        )
        optional_kwarg_sets.append(
            dict(**tools_kwargs, extend_system_message=AGENT_PERSISTENCE_GUIDANCE)
        )
        optional_kwarg_sets.append(dict(**tools_kwargs, max_failures=8))
        optional_kwarg_sets.append(dict(**tools_kwargs))

    # If the tools/controller kwarg itself isn't accepted by this
    # browser-use version, fall back further to browser-only mode rather
    # than failing to start the agent at all.
    optional_kwarg_sets.extend([
        dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE, max_failures=8),
        dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE),
        dict(max_failures=8),
        dict(),
    ])

    last_error = None

    for extra_kwargs in optional_kwarg_sets:
        try:
            agent = Agent(**base_kwargs, **extra_kwargs)

            if extra_kwargs:
                print(f"  Agent options: {list(extra_kwargs)}")

            return agent

        except TypeError as e:
            last_error = e
            continue

    raise last_error


async def run_agent(agent):
    """
    Run the agent with a larger step budget when supported, falling
    back to the default if this browser-use version doesn't accept
    max_steps on run().
    """

    try:
        return await agent.run(max_steps=50)
    except TypeError:
        return await agent.run()


# ==========================================================
# TASK INPUT
# ==========================================================

def get_ui_task():

    task = os.getenv("AGENT_TASK", "").strip()

    if task:
        return task

    try:
        if not sys.stdin.isatty():
            data = sys.stdin.read().strip()
            if data:
                return data
    except Exception:
        pass

    return ""


# ==========================================================
# MAIN
#
# Runs as a persistent loop: it never exits after a single task.
# Once one task finishes (or fails), it asks for the next one. Type
# 'exit' / 'quit', or press Ctrl+C, to actually stop the process.
# ==========================================================

async def main():

    print_startup_banner(len(llm._candidates))
    print(_boxed(["Terminal access folder:", SCRIPT_DIR[:BANNER_WIDTH - 6]]))

    tools = _build_tools()

    print(_boxed(["Persistent mode: running until you type 'exit'"]))

    # Only the very first task may come from AGENT_TASK / piped stdin.
    # Every task after that is asked for interactively -- otherwise a
    # fixed AGENT_TASK env var or an exhausted stdin pipe would either
    # loop forever on the same task or spin with nothing to do.
    pending_task = get_ui_task()

    while True:
        if pending_task:
            task = pending_task
            pending_task = None
        else:
            try:
                task = input(
                    "\nEnter the next task (or 'exit' to quit):\n> "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nShutting down.")
                break

        if not task:
            continue

        if task.lower() in {"exit", "quit"}:
            print("\nShutting down.")
            break

        print("\nTask received. Starting agent...\n")

        try:
            agent = build_agent(task, tools=tools)
            result = await run_agent(agent)

            print()
            print(_boxed(["FINAL RESULT"]))
            print(result)

        except Exception as e:
            print()
            print(_boxed(["AGENT ERROR", "", repr(e)[:BANNER_WIDTH - 6]]))
            print("  Continuing -- ready for the next task.")


if __name__ == "__main__":
    asyncio.run(main())