import test from 'node:test';
import assert from 'node:assert/strict';
import { HeadShakeDetector, parseOptions, findAnimationHotkey, watchSession, VtsApi } from '../../vts-petal-trigger.mjs';
import { WebSocketServer } from 'ws';
const defaults = parseOptions(['--model-name','ExampleModel','--token-file','/unused/token.json']);
function series(pose, options={}) {
 const d=new HeadShakeDetector(options),fires=[];
 for(let frame=0;frame<180;frame++) {const t=frame/15; const sample={time:t*1000,found:true,x:0,z:0,...pose(t,frame)};if(d.sample(sample))fires.push(t*1000);}
 return fires;
}
const shake=t=>t<1?0:20*Math.sin((t-1)*2*Math.PI*2);
test('static, slow movement and camera noise never trigger',()=>{
 for(const pose of[t=>({x:0}),t=>({x:15*Math.sin(t*2*Math.PI/5)}),t=>({x:Math.sin(t*17)*.8,z:Math.cos(t*13)*.7})])assert.deepEqual(series(pose),[]);
});
test('both yaw and roll shakes trigger with a cooldown',()=>{
 for(const axis of['x','z']){const fires=series(t=>({[axis]:shake(t)}));assert.ok(fires.length>=2);for(let i=1;i<fires.length;i++)assert.ok(fires[i]-fires[i-1]>=4500);}
});
test('a quick turn followed by a long hold and return is not a shake',()=>{
 assert.deepEqual(series(t=>({x:t<1?0:t<1.2?100*(t-1):t<3?20:t<3.2?20-100*(t-3):0})),[]);
});
test('lost tracking, resumed discontinuity and large sampling gaps discard history',()=>{
 assert.deepEqual(series(t=>({found:t<1||t>=2,x:t<2?shake(t):25})),[]);
 const detector=new HeadShakeDetector();for(let t=0;t<1000;t+=67)detector.sample({time:t,found:true,x:0,z:0});
 assert.equal(detector.sample({time:2200,found:true,x:30,z:0}),false);
 assert.equal(detector.sample({time:2267,found:true,x:-30,z:0}),false);
 detector.reset();assert.equal(detector.sample({time:5000,found:true,x:30,z:0}),false);
});
test('invalid or missing values cannot trigger and cooldown survives resets',()=>{
 const d=new HeadShakeDetector();for(let t=0;t<3000;t+=67)d.sample({time:t,found:true,x:shake(t/1000),z:0});const next=d.nextAllowed;assert.ok(next>3000);
 d.reset();assert.equal(d.nextAllowed,next);assert.equal(d.sample({time:3100,found:true,x:NaN,z:0}),false);
});
test('only one matching one-time animation hotkey is selected',()=>{
 const h={type:'TriggerAnimation',file:'motions\\PetalScatter.motion3.json',hotkeyID:'h'};
 assert.equal(findAnimationHotkey({availableHotkeys:[h]},defaults.motionFile),'h');
 assert.equal(findAnimationHotkey({availableHotkeys:[h,h]},defaults.motionFile),null);
 assert.equal(findAnimationHotkey({availableHotkeys:[{...h,type:'ChangeIdleAnimation'}]},defaults.motionFile),null);
});
test('CLI rejects invalid network and timing arguments',()=>{
 for(const extra of[['--host','host/path'],['--port','8001.1'],['--poll-ms','0'],['--velocity','NaN']])assert.throws(()=>parseOptions(['--model-name','m','--token-file','/t',...extra]));
});
async function session(mode) {
 const controller=new AbortController();let time=0,rechecking=false,calls=[];
 const api={request:async(type,data)=>{
  calls.push({type,data,time});
  const goodModel=mode!=='wrong-model';
  const matching={modelLoaded:true,modelID:'model-one',modelName:goodModel?'ExampleModel':'Other'};
  if(type==='InputParameterListRequest')return{...matching,defaultParameters:[{name:'FaceAngleX',value:shake(time/1000)},{name:'FaceAngleZ',value:0}]};
  if(type==='FaceFoundRequest')return{found:mode!=='no-face'&&!(rechecking&&mode==='face-lost-at-trigger')};
  if(type==='HotkeysInCurrentModelRequest')return{...matching,availableHotkeys:[{type:'TriggerAnimation',file:defaults.motionFile,hotkeyID:'only-flower-key'}]};
  if(type==='CurrentModelRequest'){rechecking=true;return mode==='switch-at-trigger'?{...matching,modelID:'model-two'}:matching;}
  if(type==='HotkeyTriggerRequest')return{hotkeyID:data.hotkeyID};
  throw Error(type);
 }};
 await watchSession(api,{...defaults,dryRun:mode==='dry-run'},new HeadShakeDetector(defaults),{signal:controller.signal,now:()=>time,log:()=>{},wait:async ms=>{time+=Math.max(ms,67);rechecking=false;if(time>=3500)controller.abort();}});
 return calls;
}
test('session plays only the flower hotkey and never writes tracking parameters',async()=>{
 const calls=await session('normal');assert.equal(calls.filter(c=>c.type==='HotkeyTriggerRequest').length,1);assert.equal(calls.find(c=>c.type==='HotkeyTriggerRequest').data.hotkeyID,'only-flower-key');assert.ok(!calls.some(c=>/Inject|Creation|Activation/.test(c.type)));
});
test('wrong model, no face, model-switch race, face loss and dry-run never play',async()=>{
 for(const mode of['wrong-model','no-face','switch-at-trigger','face-lost-at-trigger','dry-run'])assert.equal((await session(mode)).filter(c=>c.type==='HotkeyTriggerRequest').length,0,mode);
});
test('ws transport correlates responses, masks API error detail and times out',async()=>{
 const server=new WebSocketServer({host:'127.0.0.1',port:0});await new Promise(resolve=>server.once('listening',resolve));
 server.on('connection',socket=>socket.on('message',raw=>{const r=JSON.parse(raw);if(r.messageType==='IgnoredRequest')return;
 socket.send(JSON.stringify({requestID:r.requestID,messageType:r.messageType==='DeniedRequest'?'APIError':r.messageType.replace(/Request$/,'Response'),data:r.messageType==='DeniedRequest'?{errorID:50,message:'secret must never be shown'}:{modelID:r.data.testID}}));}));
 const api=await VtsApi.connect('127.0.0.1',server.address().port);
 try {
  const results=await Promise.all([api.request('CurrentModelRequest',{testID:'first'}),api.request('CurrentModelRequest',{testID:'second'})]);assert.deepEqual(results,[{modelID:'first'},{modelID:'second'}]);
  await assert.rejects(api.request('DeniedRequest'),error=>error.message.includes('50')&&!error.message.includes('secret'));
  await assert.rejects(api.request('IgnoredRequest',{},20),/timed out/);
 }finally{api.close();for(const client of server.clients)client.close();await new Promise(resolve=>server.close(resolve));}
});
test('313ms cadence still detects a substantial fast reversal, while slow turns do not',()=>{
 for(const kind of['shake','slow']){const d=new HeadShakeDetector(),fires=[];let t=0;for(let i=0;i<50;i++,t+=313){const x=t<1000?0:25*Math.sin((t-1000)/1000*2*Math.PI*(kind==='shake'?1.2:.15));if(d.sample({time:t,found:true,x,z:0}))fires.push(t);}if(kind==='shake'){assert.ok(fires.length>0);for(let i=1;i<fires.length;i++)assert.ok(fires[i]-fires[i-1]>=4500);}else assert.deepEqual(fires,[]);}
});
