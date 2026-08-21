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
#     "Only call `done` with success=true once you have concrete, "
#     "verifiable evidence for the answer. Only call `done` with "
#     "success=false after you have exhausted the reasonable strategies "
#     "available to you, and explain specifically what you tried and "
#     "why each attempt did not resolve the task."
# )


# def build_agent(task):
#     """
#     Construct the browser-use Agent with persistence guidance and a
#     higher failure budget, falling back gracefully if the installed
#     browser-use version doesn't support one of these kwargs.
#     """

#     base_kwargs = dict(
#         task=task,
#         llm=llm,
#         use_vision=True,
#         max_actions_per_step=10,
#     )

#     optional_kwarg_sets = [
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
# # ==========================================================

# async def main():

#     print_startup_banner(len(llm._candidates))

#     task = get_ui_task()

#     if not task:
#         task = input(
#             "Enter the task you want the agent to perform:\n> "
#         ).strip()

#     if not task:
#         print("\nNo task entered.")
#         return

#     print("\nTask received. Starting agent...\n")

#     agent = build_agent(task)

#     try:
#         result = await run_agent(agent)
#     except Exception as e:
#         print()
#         print(_boxed(["AGENT ERROR", "", repr(e)[:BANNER_WIDTH - 6]]))
#         raise

#     print()
#     print(_boxed(["FINAL RESULT"]))
#     print(result)


# if __name__ == "__main__":
#     asyncio.run(main())



import asyncio
import itertools
import json
import os
import re
import sys
from typing import Any, get_args, get_origin


def _configure_utf8_stdio():
    """Avoid Windows cp1252 failures when model/history text contains Unicode."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


_configure_utf8_stdio()


from browser_use import Agent
from browser_use.llm.views import ChatInvokeCompletion


# ==========================================================
# NIZAM AGENT 1 — EXHAUSTIVE MULTI-PROVIDER LLM ADAPTER
# ==========================================================

BANNER_WIDTH = 64
SPINNER_FRAMES = "|/-\\"
PROGRESS_BAR_LEN = 30


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
                    value = item.get("text")
                    if value:
                        parts.append(str(value))
                else:
                    value = getattr(item, "text", None)
                    if value:
                        parts.append(str(value))
                    else:
                        value = getattr(item, "value", None)
                        if value:
                            parts.append(str(value))
            return "\n".join(parts)
        return str(content)

    def _convert_messages(self, messages):
        converted = []
        for message in messages:
            message_type = type(message).__name__
            content = self._content_to_text(getattr(message, "content", ""))

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
        # anything. The user asked for exhaustive checking.
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

        cleaned.sort(key=lambda x: (preferred.get(x[0], 100), x[0], x[1]))

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

    def _request_one(self, index, provider_name, model, messages):
        """
        Execute exactly one provider/model request.

        Each candidate gets its own G4F Client instance so the requests can
        safely be executed in parallel threads.
        """
        key = (provider_name, model)

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
            }

        except Exception as e:
            error_text = f"{type(e).__name__}: {e}"

            return {
                "ok": False,
                "provider": provider_name,
                "model": model,
                "response": None,
                "text": "",
                "error": error_text,
                "key": key,
            }

        finally:
            self._completed_count += 1

    async def _request_all_concurrently(self, messages):
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
                })
            else:
                normalized.append(result)

        success_count = sum(
            1 for result in normalized if result["ok"]
        )

        print(
            f"  {success_count}/{len(normalized)} model sources responded."
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

    async def _request(self, messages, output_format=None):
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
        merely answered fastest.
        """

        results = await self._request_all_concurrently(messages)

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

                    print(
                        f"  -> Using {result['provider']} / "
                        f"{result['model']}"
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

                print(
                    f"  -> Using {result['provider']} / {result['model']}"
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
        lc_messages = self._convert_messages(messages)

        if output_format is not None:
            schema = output_format.model_json_schema()

            schema_instruction = (
                "\n\nIMPORTANT: Return ONLY valid JSON. "
                "Do not use markdown fences or explanatory text. "
                "The JSON MUST conform exactly to this schema:\n"
                + json.dumps(schema, ensure_ascii=False)
            )

            if lc_messages:
                lc_messages = list(lc_messages)
                lc_messages[-1] = dict(lc_messages[-1])
                lc_messages[-1]["content"] = (
                    str(lc_messages[-1].get("content", ""))
                    + schema_instruction
                )

        selected, parsed_result = await self._request(
            lc_messages,
            output_format=output_format,
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
# alongside its browser actions. Every command runs with its working
# directory fixed to the folder this script lives in.
#
# NOTE on scope: fixing cwd only sets the *starting* directory for the
# command. A command that itself does `cd ..` or references an absolute
# path elsewhere is not blocked -- there is no filesystem sandbox/chroot
# here, just a scoped starting point. Only run this with tasks you trust.
# ==========================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _build_controller():
    """
    Register a terminal-command action on a browser-use Controller.

    Returns None (instead of raising) if the installed browser-use version
    doesn't expose Controller/actions the way this code expects, so the
    agent still runs in browser-only mode rather than crashing on startup.
    """

    try:
        from browser_use import Controller
    except Exception as e:
        print(f"  Terminal-access tool unavailable (no Controller): {e}")
        return None

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
        controller = Controller()

        @controller.action(
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

        return controller

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


def build_agent(task, controller=None):
    """
    Construct the browser-use Agent with persistence guidance, terminal
    access, and a higher failure budget, falling back gracefully if the
    installed browser-use version doesn't support one of these kwargs.
    """

    base_kwargs = dict(
        task=task,
        llm=llm,
        use_vision=True,
        max_actions_per_step=10,
    )

    controller_kwargs = (
        dict(controller=controller) if controller is not None else {}
    )

    optional_kwarg_sets = [
        dict(
            **controller_kwargs,
            extend_system_message=AGENT_PERSISTENCE_GUIDANCE,
            max_failures=8,
        ),
        dict(**controller_kwargs, extend_system_message=AGENT_PERSISTENCE_GUIDANCE),
        dict(**controller_kwargs, max_failures=8),
        dict(**controller_kwargs),
        # If the controller kwarg itself isn't accepted by this browser-use
        # version, fall back further to browser-only mode rather than
        # failing to start the agent at all.
        dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE, max_failures=8),
        dict(extend_system_message=AGENT_PERSISTENCE_GUIDANCE),
        dict(max_failures=8),
        dict(),
    ]

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

    controller = _build_controller()

    print(_boxed(["Persistent mode: running until you type 'exit'"]))

    # Only the very first task may come from AGENT_TASK / piped stdin.
    # Every task after that is asked for interactively -- otherwise a
    # fixed AGENT_TASK env var or an exhausted stdin pipe would either
    # loop forever on the same task or spin with nothing to do.
    pending_task = get_ui_task()
    # A supervisor-managed invocation has exactly one AGENT_TASK and no
    # interactive stdin; exit after it so the parent can collect the result.
    one_shot = bool(os.getenv("SUPERVISOR_MANAGED"))

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
            agent = build_agent(task, controller=controller)
            result = await run_agent(agent)

            print()
            print(_boxed(["FINAL RESULT"]))
            print(result)

        except Exception as e:
            print()
            print(_boxed(["AGENT ERROR", "", repr(e)[:BANNER_WIDTH - 6]]))
            print("  Continuing -- ready for the next task.")

        if one_shot:
            break


if __name__ == "__main__":
    asyncio.run(main())
