"""The Gemini adapter, against canned streamed responses (no API calls)."""
import asyncio
import io
import json
import unittest
from unittest import mock

from clocktower.llm import NO_LIMIT, GeminiConversation, Ledger, conversation

SCHEMA = {'type': 'object', 'properties': {'say': {'type': 'string'}}, 'required': ['say']}


def sse(*chunks):
    return io.BytesIO(b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks))


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def stream(*chunks):
    return FakeResp(sse(*chunks).getvalue())


def part(text, thought=False, sig=None):
    p = {'text': text}
    if thought:
        p['thought'] = True
    if sig:
        p['thoughtSignature'] = sig
    return {'candidates': [{'content': {'role': 'model', 'parts': [p]}}]}


USAGE = {'usageMetadata': {'promptTokenCount': 1000, 'cachedContentTokenCount': 800, 'candidatesTokenCount': 20,
                           'thoughtsTokenCount': 300}}


class GeminiTest(unittest.TestCase):
    def conv(self, tmp):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'k'}):
            return conversation(None, 'system', SCHEMA, model='gemini-4-neon', label='Alex',
                                ledger=Ledger(tmp + '/ledger.jsonl'), semaphore=NO_LIMIT)

    def test_turn_keeps_thoughts_and_signatures_and_prices_usage(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        c = self.conv(tmp)
        self.assertIsInstance(c, GeminiConversation)
        calls = []
        chunks = [part('I suspect ', thought=True), part('Blair.', thought=True, sig='SIG1'),
                  part('{"say": '), part('"hi"}'), {'candidates': [{'finishReason': 'STOP'}], **USAGE}]

        def urlopen(req, timeout=None, context=None):
            calls.append(json.loads(req.data))
            return stream(*chunks)
        with mock.patch('urllib.request.urlopen', urlopen):
            r = asyncio.run(c.send('your turn'))
        self.assertEqual(r.action, {'say': 'hi'})
        self.assertEqual(r.thinking, 'I suspect Blair.')
        model_turn = c.messages[-1]
        self.assertEqual(model_turn['role'], 'model')
        self.assertEqual(model_turn['parts'][0], {'text': 'I suspect Blair.', 'thought': True, 'thoughtSignature': 'SIG1'})
        self.assertEqual(model_turn['parts'][1], {'text': '{"say": "hi"}'})
        cfg = calls[0]['generationConfig']
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'high')
        self.assertEqual(cfg['responseJsonSchema'], SCHEMA)
        self.assertEqual(cfg['maxOutputTokens'], 8000)
        # 200 uncached input at $3, 800 cached at $0.30, 320 output (thinking included) at $15
        self.assertAlmostEqual(c.ledger.spent, (200 * 3 + 800 * 0.30 + 320 * 15) / 1e6)

    def test_ceiling_retries_once_at_low_then_passes(self):
        import tempfile
        c = self.conv(tempfile.mkdtemp())
        levels = []

        def urlopen(req, timeout=None, context=None):
            levels.append(json.loads(req.data)['generationConfig']['thinkingConfig']['thinkingLevel'])
            return stream(part('...', thought=True), {'candidates': [{'finishReason': 'MAX_TOKENS'}], **USAGE})
        with mock.patch('urllib.request.urlopen', urlopen):
            r = asyncio.run(c.send('your turn'))
        self.assertEqual(levels, ['high', 'low'])
        self.assertEqual(r.action, {})


if __name__ == '__main__':
    unittest.main()
