const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');

function setup({ onTurn = async () => 'Verified answer', microphone } = {}) {
  const sent = [], states = [], errors = [], transcripts = [];
  const track = { enabled: true, stop() { this.stopped = true; } };
  const stream = { getTracks: () => [track], getAudioTracks: () => [track] };
  const channel = { readyState: 'open', send: data => sent.push(JSON.parse(data)), close() { this.closed = true; } };
  const audio = { play: async () => {}, pause() {}, srcObject: null };
  class PC {
    createDataChannel() { return channel; }
    addTrack() {}
    async createOffer() { return { sdp: 'v=0' }; }
    async setLocalDescription() {}
    async setRemoteDescription() { channel.onopen(); }
    close() {}
  }
  const context = { exports: {}, navigator: { mediaDevices: { getUserMedia: microphone || (async () => stream) } },
    RTCPeerConnection: PC, AbortController, DOMException, setTimeout, clearTimeout,
    fetch: async () => ({ ok: true, text: async () => 'answer' }) };
  const source = ts.transpileModule(fs.readFileSync(__dirname + '/voice-session.ts', 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInNewContext(source, context);
  const session = new context.exports.VoiceSession({ endpoint: '/session', audio, onTurn,
    onState: state => states.push(state), onError: error => errors.push(error), onTranscript: text => transcripts.push(text) });
  return { session, track, stream, channel, sent, states, errors, transcripts,
    event: value => channel.onmessage({ data: JSON.stringify(value) }) };
}
const tick = () => new Promise(resolve => setTimeout(resolve, 10));

test('mute disables microphone, unmute enables it, end releases it', async () => {
  const s = setup(); await s.session.start();
  s.session.setMuted(true); assert.equal(s.track.enabled, false);
  s.session.setMuted(false); assert.equal(s.track.enabled, true);
  s.session.stop(); assert.equal(s.track.stopped, true); assert.equal(s.channel.closed, true);
  assert.equal(s.states.at(-1), 'idle');
});

test('duplicate transcripts create only one planner turn', async () => {
  let calls = 0;
  const s = setup({ onTurn: async () => { calls++; return 'answer'; } });
  await s.session.start();
  const event = { type: 'conversation.item.input_audio_transcription.completed', item_id: 'one', transcript: 'Next games?' };
  s.event(event); s.event(event); await tick();
  assert.equal(calls, 1); assert.equal(s.sent.filter(x => x.type === 'response.create').length, 1);
  s.session.stop();
});

test('ending while planner is running suppresses late playback', async () => {
  let resolve;
  const s = setup({ onTurn: () => new Promise(r => { resolve = r; }) });
  await s.session.start();
  s.event({ type: 'conversation.item.input_audio_transcription.completed', item_id: 'one', transcript: 'Hello' });
  s.session.stop(); resolve('late reply'); await tick();
  assert.equal(s.sent.some(x => x.type === 'response.create'), false);
});

test('end during microphone permission prompt releases late stream', async () => {
  let resolve;
  const s = setup({ microphone: () => new Promise(r => { resolve = r; }) });
  const pending = s.session.start(); s.session.stop(); resolve(s.stream); await pending;
  assert.equal(s.track.stopped, true);
});

test('interrupt cancels generation and clears playback', async () => {
  const s = setup(); await s.session.start();
  s.event({ type: 'response.created' }); s.session.interrupt();
  assert.ok(s.sent.some(x => x.type === 'response.cancel'));
  assert.ok(s.sent.some(x => x.type === 'output_audio_buffer.clear'));
  s.session.stop();
});

test('muted speech never reaches the planner', async () => {
  let calls = 0;
  const s = setup({ onTurn: async () => { calls++; } }); await s.session.start();
  s.session.setMuted(true);
  s.event({ type: 'input_audio_buffer.speech_started', item_id: 'muted' });
  s.session.setMuted(false);
  s.event({ type: 'conversation.item.input_audio_transcription.completed', item_id: 'muted', transcript: 'Private' });
  await tick(); assert.equal(calls, 0); s.session.stop();
});

test('muting an in-progress utterance rejects its delayed transcript', async () => {
  let calls = 0;
  const s = setup({ onTurn: async () => { calls++; } }); await s.session.start();
  s.event({ type: 'input_audio_buffer.speech_started', item_id: 'partial' });
  s.session.setMuted(true); s.session.setMuted(false);
  s.event({ type: 'conversation.item.input_audio_transcription.completed', item_id: 'partial', transcript: 'Discard this' });
  await tick(); assert.equal(calls, 0); s.session.stop();
});

test('follow-up turns run sequentially and superseded replies are not spoken', async () => {
  const calls = []; let resolve;
  const s = setup({ onTurn: text => {
    calls.push(text);
    return text === 'First' ? new Promise(r => { resolve = r; }) : Promise.resolve('Second answer');
  } });
  await s.session.start();
  s.event({ type: 'conversation.item.input_audio_transcription.completed', item_id: 'one', transcript: 'First' });
  s.event({ type: 'input_audio_buffer.speech_started', item_id: 'two' });
  s.event({ type: 'conversation.item.input_audio_transcription.completed', item_id: 'two', transcript: 'Second' });
  assert.deepEqual(calls, ['First']); resolve('First answer'); await tick(); await tick();
  assert.deepEqual(calls, ['First', 'Second']);
  const replies = s.sent.filter(x => x.type === 'response.create');
  assert.equal(replies.length, 1); assert.ok(replies[0].response.instructions.includes('Second answer'));
  s.session.stop();
});
