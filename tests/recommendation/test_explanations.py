"""Evidence-bound optional wording; all provider calls are local test doubles."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from threading import Event
from time import perf_counter
import unittest

from backend.ai.config import DEFAULT_EXPLANATION_CONFIG, ExplanationConfig
from backend.ai.explanations import enrich_recommendations
from backend.recommendation.engine import recommend
from test_engine import AS_OF, employee, event, participation, profiles


TEST_ENV = {"OPENAI_API_KEY": "test-only-placeholder-key"}


def engine_result(*, person=None, catalog=None, history=None):
    if catalog is None:
        catalog = [
            event("focused-systems"),
            event("combined-skills", {"system-design": 1, "public-speaking": 1}),
            event("speaking-session", {"public-speaking": 1}, type="meetup",
                  format="offline", upcoming_sessions=[AS_OF]),
        ]
    return recommend(employee() if person is None else person, profiles(), catalog,
                     [] if history is None else history, as_of=AS_OF)


def provider_input(payload):
    """Read the public request envelope, not provider implementation internals."""
    messages = payload["input"]
    if isinstance(messages, str):
        return json.loads(messages)
    user_message = next(message for message in messages if message["role"] == "user")
    content = user_message["content"]
    text = content if isinstance(content, str) else "".join(item["text"] for item in content)
    return json.loads(text)


def valid_choices(payload, variant="coaching"):
    request = provider_input(payload)
    return {
        "language": request["language"],
        "explanations": [{
            "event_id": recommendation["event_id"],
            "fact_variants": [{"fact_id": fact["fact_id"], "variant": variant}
                              for fact in recommendation["facts"]],
        } for recommendation in request["recommendations"]],
    }


def completed_response(value):
    return {
        "status": "completed",
        "output": [{
            "type": "message", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": json.dumps(value), "annotations": []}],
        }],
    }


def success_transport(payload, *, api_key, timeout_seconds):
    return completed_response(valid_choices(payload))


def stripped_result(value):
    result = deepcopy(value)
    result.pop("explanation_summary", None)
    result.pop("explanation_meta", None)
    for recommendation in result["recommendations"]:
        recommendation.pop("explanation", None)
    return result


class ExplanationTests(unittest.TestCase):
    def enrich(self, result=None, **kwargs):
        return enrich_recommendations(engine_result() if result is None else result, **kwargs)

    def assert_engine_preserved(self, original, enriched):
        self.assertEqual(stripped_result(enriched), stripped_result(original))

    def assert_deterministic_fallback(self, original, enriched, status, language="ru"):
        expected = self.enrich(original, preferred_language=language, use_openai=False, environ={})
        self.assert_engine_preserved(original, enriched)
        self.assertEqual(enriched["explanation_meta"]["provider_status"], status)
        self.assertEqual(enriched["explanation_summary"], expected["explanation_summary"])
        self.assertEqual([item["explanation"] for item in enriched["recommendations"]],
                         [item["explanation"] for item in expected["recommendations"]])
        self.assertTrue(all(item["explanation"]["source"] == "deterministic"
                            for item in enriched["recommendations"]))

    def test_default_is_local_and_preserves_every_engine_field(self):
        original = engine_result()
        before = deepcopy(original)

        def forbidden(*args, **kwargs):
            self.fail("Disabled OpenAI must never call its transport")

        result = self.enrich(original, environ=TEST_ENV, transport=forbidden)
        self.assertEqual(original, before)
        self.assert_engine_preserved(original, result)
        self.assertIsNot(result, original)
        self.assertEqual(result["explanation_meta"]["provider_status"], "disabled")
        self.assertFalse(result["explanation_meta"]["openai_requested"])
        self.assertEqual(result["explanation_summary"]["source"], "deterministic")
        self.assertTrue(result["explanation_summary"]["text"].strip())
        self.assertEqual(len(result["recommendations"]), 3)
        for recommendation in result["recommendations"]:
            self.assertEqual(recommendation["explanation"]["source"], "deterministic")
            self.assertTrue(recommendation["explanation"]["text"].strip())

    def test_russian_english_and_kazakh_are_localized_without_ai(self):
        texts = {}
        for language in ("ru", "en", "kk"):
            with self.subTest(language=language):
                result = self.enrich(preferred_language=language, environ={})
                meta = result["explanation_meta"]
                self.assertEqual(meta["requested_language"], language)
                self.assertEqual(meta["language"], language)
                self.assertFalse(meta["language_fallback"])
                self.assertEqual(result["explanation_summary"]["language"], language)
                self.assertTrue(all(item["explanation"]["language"] == language
                                    for item in result["recommendations"]))
                texts[language] = result["recommendations"][0]["explanation"]["text"]
        self.assertEqual(len(set(texts.values())), 3)

    def test_unsupported_language_falls_back_to_russian_explicitly(self):
        result = self.enrich(preferred_language="unseen-language", environ={})
        russian = self.enrich(preferred_language="ru", environ={})
        self.assertEqual(result["explanation_meta"]["requested_language"], "unseen-language")
        self.assertEqual(result["explanation_meta"]["language"], "ru")
        self.assertTrue(result["explanation_meta"]["language_fallback"])
        self.assertEqual(result["explanation_summary"], russian["explanation_summary"])
        self.assertEqual([r["explanation"] for r in result["recommendations"]],
                         [r["explanation"] for r in russian["recommendations"]])

    def test_facts_and_segments_have_exact_local_traceability(self):
        result = self.enrich(environ={})
        explanations = [result["explanation_summary"]] + [r["explanation"] for r in result["recommendations"]]
        for explanation in explanations:
            facts = explanation["facts"]
            segments = explanation["segments"]
            self.assertTrue(facts)
            fact_ids = [fact["fact_id"] for fact in facts]
            self.assertEqual(len(fact_ids), len(set(fact_ids)))
            self.assertEqual([segment["fact_id"] for segment in segments], fact_ids)
            for fact in facts:
                self.assertTrue(fact["code"])
                self.assertIn("values", fact)
                self.assertTrue(fact["evidence_paths"])
                self.assertTrue(all(isinstance(path, str) and path for path in fact["evidence_paths"]))
            self.assertTrue(all(segment["text"].strip() for segment in segments))

    def test_missing_key_falls_back_without_calling_transport(self):
        original = engine_result()

        def forbidden(*args, **kwargs):
            self.fail("Missing credentials must not call provider transport")

        result = self.enrich(original, use_openai=True, environ={}, transport=forbidden)
        self.assert_deterministic_fallback(original, result, "missing_api_key")
        self.assertTrue(result["explanation_meta"]["openai_requested"])

    def test_success_only_selects_local_coaching_phrases(self):
        original = engine_result()
        local = self.enrich(original, environ={})
        captured = {}

        def transport(payload, *, api_key, timeout_seconds):
            captured["request"] = deepcopy(provider_input(payload))
            captured["api_key"] = api_key
            captured["timeout_seconds"] = timeout_seconds
            return completed_response(valid_choices(payload, "coaching"))

        enriched = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=transport)
        self.assert_engine_preserved(original, enriched)
        self.assertEqual(enriched["explanation_meta"]["provider_status"], "used")
        self.assertEqual(captured["api_key"], TEST_ENV["OPENAI_API_KEY"])
        self.assertEqual(captured["timeout_seconds"], DEFAULT_EXPLANATION_CONFIG.timeout_seconds)
        self.assertEqual(enriched["explanation_summary"], local["explanation_summary"])
        for recommendation, local_recommendation, requested in zip(
                enriched["recommendations"], local["recommendations"], captured["request"]["recommendations"]):
            explanation = recommendation["explanation"]
            self.assertEqual(explanation["source"], "openai")
            self.assertEqual(explanation["facts"], local_recommendation["explanation"]["facts"])
            self.assertEqual([segment["text"] for segment in explanation["segments"]],
                             [fact["variants"]["coaching"] for fact in requested["facts"]])
        self.assertNotEqual([r["explanation"]["text"] for r in enriched["recommendations"]],
                            [r["explanation"]["text"] for r in local["recommendations"]])

    def test_provider_can_select_direct_phrases_without_changing_facts(self):
        original = engine_result()
        local = self.enrich(original, environ={})

        def transport(payload, **kwargs):
            return completed_response(valid_choices(payload, "direct"))

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=transport)
        self.assertEqual(result["explanation_meta"]["provider_status"], "used")
        for actual, expected in zip(result["recommendations"], local["recommendations"]):
            self.assertEqual(actual["explanation"]["text"], expected["explanation"]["text"])
            self.assertEqual(actual["explanation"]["facts"], expected["explanation"]["facts"])

    def test_successful_kazakh_and_english_keep_requested_language(self):
        for language in ("kk", "en"):
            with self.subTest(language=language):
                result = self.enrich(preferred_language=language, use_openai=True,
                                     environ=TEST_ENV, transport=success_transport)
                self.assertEqual(result["explanation_meta"]["provider_status"], "used")
                self.assertTrue(all(item["explanation"]["language"] == language
                                    for item in result["recommendations"]))

    def test_provider_payload_excludes_employee_and_participation_details(self):
        original = engine_result(history=[participation(
            "private-history-record-731", "speaking-session", "dropped",
            feedback_rating=2, score=None, feedback_text="private free-text sentinel",
        )])
        original["career_state"]["backend_private_note"] = "backend-private-note-sentinel"
        original["recommendations"][0]["history_signals"]["record_evidence"] = [
            {"record_id": "private-detailed-id-819", "private_note": "private-detail-sentinel"},
        ]
        captured = {}

        def transport(payload, **kwargs):
            captured["payload"] = deepcopy(payload)
            return completed_response(valid_choices(payload))

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=transport)
        self.assertEqual(result["explanation_meta"]["provider_status"], "used")
        request = provider_input(captured["payload"])
        self.assertEqual(set(request), {"language", "recommendations"})
        for recommendation in request["recommendations"]:
            self.assertEqual(set(recommendation), {"event_id", "facts"})
            for fact in recommendation["facts"]:
                self.assertEqual(set(fact), {"fact_id", "variants"})
                self.assertEqual(set(fact["variants"]), {"direct", "coaching"})
        serialized = json.dumps(captured["payload"], ensure_ascii=False)
        for private_value in (original["employee_id"], "private-history-record-731", "private free-text sentinel",
                              "backend-private-note-sentinel", "private-detailed-id-819", "private-detail-sentinel",
                              TEST_ENV["OPENAI_API_KEY"]):
            self.assertNotIn(private_value, serialized)
        self.assert_engine_preserved(original, result)

    def test_provider_payload_mutation_cannot_mutate_engine_input(self):
        original = engine_result()
        before = deepcopy(original)

        def transport(payload, **kwargs):
            response = completed_response(valid_choices(payload))
            payload.clear()
            payload["mutated_by_provider"] = True
            return response

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=transport)
        self.assertEqual(original, before)
        self.assert_engine_preserved(original, result)
        self.assertEqual(result["explanation_meta"]["provider_status"], "used")

    def test_provider_exception_returns_safe_fallback_without_error_or_secret(self):
        original = engine_result()
        private_error = "private HTTP body containing account details"

        def broken(*args, **kwargs):
            raise RuntimeError(private_error + TEST_ENV["OPENAI_API_KEY"])

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=broken)
        self.assert_deterministic_fallback(original, result, "api_error")
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(private_error, serialized)
        self.assertNotIn(TEST_ENV["OPENAI_API_KEY"], serialized)

    def test_timeout_exception_falls_back(self):
        original = engine_result()

        def timeout(*args, **kwargs):
            raise TimeoutError("private timeout details")

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=timeout)
        self.assert_deterministic_fallback(original, result, "timeout")
        self.assertNotIn("private timeout details", json.dumps(result))

    def test_deadline_is_enforced_even_when_transport_ignores_timeout(self):
        original = engine_result()
        release = Event()
        transport_finished = Event()
        config = replace(DEFAULT_EXPLANATION_CONFIG, timeout_seconds=0.02)

        def slow_transport(payload, **kwargs):
            try:
                release.wait(0.3)
                return completed_response(valid_choices(payload))
            finally:
                transport_finished.set()

        try:
            started = perf_counter()
            result = self.enrich(original, use_openai=True, environ=TEST_ENV,
                                 config=config, transport=slow_transport)
            elapsed = perf_counter() - started
        finally:
            release.set()
            self.assertTrue(transport_finished.wait(0.3))
        self.assertLess(elapsed, 0.15)
        self.assert_deterministic_fallback(original, result, "timeout")

    def test_malformed_json_falls_back_for_the_entire_batch(self):
        original = engine_result()

        def malformed(payload, **kwargs):
            response = completed_response(valid_choices(payload))
            response["output"][0]["content"][0]["text"] = "{not valid JSON"
            return response

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=malformed)
        self.assert_deterministic_fallback(original, result, "invalid_output")

    def test_invalid_top_level_shape_falls_back(self):
        original = engine_result()
        for bad in (None, [], "free prose instead of choices"):
            with self.subTest(shape=bad):
                def malformed(payload, **kwargs):
                    return completed_response(bad)
                result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=malformed)
                self.assert_deterministic_fallback(original, result, "invalid_output")

    def test_unsupported_language_event_fact_variant_and_claims_fall_back(self):
        original = engine_result()

        def wrong_language(reply):
            reply["language"] = "en"

        def wrong_event(reply):
            reply["explanations"][0]["event_id"] = "invented-event"

        def wrong_fact(reply):
            reply["explanations"][0]["fact_variants"][0]["fact_id"] = "invented-fact"

        def wrong_variant(reply):
            reply["explanations"][0]["fact_variants"][0]["variant"] = "guaranteed-promotion"

        def free_text_claim(reply):
            reply["explanations"][0]["text"] = "Promotion is guaranteed after this course."

        def altered_score(reply):
            reply["explanations"][0]["score"] = 1.0

        def altered_rank(reply):
            reply["explanations"][0]["rank"] = 99

        def extra_top_claim(reply):
            reply["summary"] = "Invented salary raise"

        for mutate in (wrong_language, wrong_event, wrong_fact, wrong_variant, free_text_claim,
                       altered_score, altered_rank, extra_top_claim):
            with self.subTest(mutation=mutate.__name__):
                def unsupported(payload, **kwargs):
                    reply = valid_choices(payload)
                    mutate(reply)
                    return completed_response(reply)
                result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=unsupported)
                self.assert_deterministic_fallback(original, result, "unsupported_output")

    def test_reordering_skipping_or_duplicating_events_or_facts_falls_back(self):
        original = engine_result()

        def reverse_events(reply):
            reply["explanations"].reverse()

        def omit_event(reply):
            reply["explanations"].pop()

        def duplicate_event(reply):
            reply["explanations"][1] = deepcopy(reply["explanations"][0])

        def reverse_facts(reply):
            reply["explanations"][0]["fact_variants"].reverse()

        def omit_fact(reply):
            reply["explanations"][0]["fact_variants"].pop()

        def duplicate_fact(reply):
            facts = reply["explanations"][0]["fact_variants"]
            facts[1] = deepcopy(facts[0])

        for mutate in (reverse_events, omit_event, duplicate_event, reverse_facts, omit_fact, duplicate_fact):
            with self.subTest(mutation=mutate.__name__):
                def unsupported(payload, **kwargs):
                    reply = valid_choices(payload)
                    mutate(reply)
                    return completed_response(reply)
                result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=unsupported)
                self.assert_deterministic_fallback(original, result, "unsupported_output")

    def test_invalid_second_recommendation_discards_valid_first_provider_wording(self):
        original = engine_result()

        def partially_valid(payload, **kwargs):
            reply = valid_choices(payload, "coaching")
            reply["explanations"][1]["fact_variants"][0]["variant"] = "unsupported"
            return completed_response(reply)

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=partially_valid)
        self.assert_deterministic_fallback(original, result, "unsupported_output")

    def test_oversized_payload_falls_back_without_calling_provider(self):
        original = engine_result()
        config = replace(DEFAULT_EXPLANATION_CONFIG, max_payload_bytes=256)

        def forbidden(*args, **kwargs):
            self.fail("Oversized payload must never reach provider transport")

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, config=config, transport=forbidden)
        self.assert_deterministic_fallback(original, result, "payload_too_large")

    def test_no_candidates_explains_diagnostics_without_provider_call(self):
        original = engine_result(catalog=[event("blocked-by-grade", target_grades=["Lead"])])

        def forbidden(*args, **kwargs):
            self.fail("Empty recommendation set must never call provider transport")

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=forbidden)
        self.assertEqual(result["status"], "no_eligible_recommendations")
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["explanation_meta"]["provider_status"], "no_recommendations")
        self.assertEqual(result["explanation_summary"]["source"], "deterministic")
        self.assertTrue(result["explanation_summary"]["facts"])
        self.assertTrue(result["explanation_summary"]["text"].strip())
        self.assert_engine_preserved(original, result)

    def test_lead_without_goal_retains_distinct_deterministic_summary(self):
        original = engine_result(person=employee(grade="Lead"), catalog=[])
        blocked = engine_result(catalog=[])
        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=success_transport)
        other_summary = self.enrich(blocked, environ={})["explanation_summary"]
        self.assertEqual(result["status"], "no_next_grade")
        self.assertIsNone(result["target"])
        self.assertEqual(result["explanation_meta"]["provider_status"], "no_recommendations")
        self.assertNotEqual(result["explanation_summary"]["text"], other_summary["text"])
        self.assert_engine_preserved(original, result)

    def test_repeated_enrichment_is_idempotent_and_input_is_not_aliased(self):
        original = engine_result()
        first = self.enrich(original, environ={})
        second = self.enrich(first, environ={})
        self.assertEqual(first, second)
        before = deepcopy(original)
        first["recommendations"][0]["simulation"]["simulated_skills_after"]["system-design"] = 99
        first["explanation_meta"]["language"] = "edited"
        self.assertEqual(original, before)
        self.assertNotEqual(first, second)

    def test_success_can_be_reenriched_locally_without_stale_ai_text(self):
        original = engine_result()
        ai_result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=success_transport)
        local_again = self.enrich(ai_result, use_openai=False, environ={})
        expected = self.enrich(original, use_openai=False, environ={})
        self.assertEqual(local_again, expected)

    def test_configuration_is_immutable_with_a_bounded_timeout(self):
        config = ExplanationConfig()
        self.assertGreater(config.timeout_seconds, 0)
        self.assertLessEqual(config.timeout_seconds, 10)
        with self.assertRaises(FrozenInstanceError):
            config.timeout_seconds = 99

    def test_environment_overrides_model_and_timeout_without_mutating_config(self):
        original = engine_result()
        config = ExplanationConfig(model="local-test-model", timeout_seconds=0.5)
        captured = {}

        def transport(payload, *, api_key, timeout_seconds):
            captured["model"] = payload["model"]
            captured["timeout_seconds"] = timeout_seconds
            return completed_response(valid_choices(payload))

        environment = dict(TEST_ENV, OPENAI_MODEL="overridden-test-model", OPENAI_TIMEOUT_SECONDS="0.2")
        result = self.enrich(original, use_openai=True, environ=environment, config=config, transport=transport)
        self.assertEqual(result["explanation_meta"]["provider_status"], "used")
        self.assertEqual(captured, {"model": "overridden-test-model", "timeout_seconds": 0.2})
        self.assertEqual(config.model, "local-test-model")
        self.assertEqual(config.timeout_seconds, 0.5)
        self.assert_engine_preserved(original, result)

    def test_invalid_optional_configuration_falls_back_before_provider_call(self):
        original = engine_result()

        def forbidden(*args, **kwargs):
            self.fail("Invalid optional AI configuration must not call its provider")

        options = [{"environ": dict(TEST_ENV, OPENAI_MODEL="invalid model")},
                   {"environ": TEST_ENV, "config": {}},
                   {"environ": []}]
        options += [{"environ": dict(TEST_ENV, OPENAI_TIMEOUT_SECONDS=value)}
                    for value in ("0", "-1", "10.01", "NaN", "Infinity", "not-a-number")]
        for kwargs in options:
            with self.subTest(configuration=kwargs):
                result = self.enrich(original, use_openai=True, transport=forbidden, **kwargs)
                self.assert_deterministic_fallback(original, result, "invalid_config")

    def test_duplicate_json_keys_and_nonfinite_constants_are_invalid_output(self):
        original = engine_result()
        invalid_texts = [
            '{"language":"ru","language":"ru","explanations":[]}',
            '{"language":NaN,"explanations":[]}',
            '{"language":"ru","explanations":Infinity}',
            '{"language":"ru","explanations":-Infinity}',
        ]
        for text in invalid_texts:
            with self.subTest(model_json=text):
                def invalid_json(payload, **kwargs):
                    response = completed_response(valid_choices(payload))
                    response["output"][0]["content"][0]["text"] = text
                    return response
                result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=invalid_json)
                self.assert_deterministic_fallback(original, result, "invalid_output")

    def test_unpaired_unicode_surrogate_in_evidence_falls_back_before_transport(self):
        person = employee()
        old_role = person["role"]
        person["role"] = "unseen-role-\ud800"
        role_profiles = profiles()
        for profile in role_profiles:
            if profile["role"] == old_role:
                profile["role"] = person["role"]
        catalog = [event("unicode-evidence-event", target_roles=[person["role"]])]
        original = recommend(person, role_profiles, catalog, [], as_of=AS_OF)
        before = deepcopy(original)

        def forbidden(*args, **kwargs):
            self.fail("Evidence that cannot be encoded as UTF-8 must not reach provider transport")

        result = self.enrich(original, use_openai=True, environ=TEST_ENV, transport=forbidden)
        self.assertEqual(original, before)
        self.assert_deterministic_fallback(original, result, "invalid_output")


if __name__ == "__main__":
    unittest.main()
