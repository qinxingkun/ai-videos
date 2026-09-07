# MiniMax-H3《三顾茅庐》完整提示词

> 来源对话: [H3 三顾茅庐](67bb2e1b-e4c3-40c0-8138-1f53706ff2a8)
> 格式: H3 `subject_definitions` + 画面/对白描述（非 JoyAI-Echo ID_A 格式）
> 共 28 条去重后的提示词块（含迭代修订版）

说明：仓库里 JoyAI 版在 `ComfyUI/.../prompts/sangu_maolu_15shots.*`；下面是 **MiniMax-H3** 实战用的提示词，原先只在对话里，现已落盘。

## Prompt 01（对话行 L272）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, a middle-aged warlord with a short dark beard, wearing a dark long robe, standing alone on a hillside.
<Subject 2> is the dusk Jingzhou wilderness from <Picture 1>, with distant beacon smoke, ruined villages, and refugees on a muddy road.
<Picture 1> is a storyboard reference for [Shot 1], defining the wide dusk landscape, beacon smoke, and refugee procession.
<Picture 2> is a storyboard reference for [Shot 2], defining Liu Bei standing alone on the high slope with the distant Jingzhou wall.
<Picture 3> is a storyboard reference for [Shot 3], defining Liu Bei's worried profile facing the horizon.

summary:
[reference generation] The target video opens on the war-torn Jingzhou dusk of <Subject 2>, then cuts to <Subject 1> alone on a hillside, ending on his uneasy profile as he delivers a voice-over about the fallen Han and his lack of a foothold.

retention_analysis:
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - Liu Bei's facial identity, dark robe, and solitary warlord presence are retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - the dusk wilderness, beacon smoke, ruined villages, and refugee line are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - viewpoint, landscape layout, and refugee placement stay aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - Liu Bei's high-slope stance and distant city wall placement stay aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - the side-profile framing and worried expression stay aligned.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama, slightly desaturated, with dusty golden-hour light and soft film grain.
[Shot 1] A slow wide establishing shot opens from <Picture 1> over <Subject 2>: dusk hills outside Jingzhou, several columns of beacon smoke rising far away, ruined villages scattered across the waste, and ragged refugees with bundles trudging along a muddy road. The camera holds mostly static with a very slight push in at slow speed as wind moves dry grass and dust.
[Shot 2] At 00:04.000, the shot cuts to a full shot matching <Picture 2>: <Subject 1>, Liu Bei in a dark long robe, stands alone atop a high slope, mountain wind lifting his robe hem, while the blurred Jingzhou city wall sits far behind him. He remains still, looking into the distance.
[Shot 3] At 00:09.000, the camera arcs slowly around <Subject 1> into a close side profile matching <Picture 3>. His brows are drawn, eyes troubled, gazing far away. Off-screen, <Subject 1> (S1) speaks in a restrained middle-aged male voice-over with grave cadence, <d>[Chinese] 天下纷乱，汉室倾颓。百姓流离，而备……至今仍无立足之地。</d> His lips stay closed while the VO continues to the final frame.

overall_soundscape:
Distant wind over dry grassland, faint refugee footsteps and muffled cart creaks in Shot 1, then quieter hillside wind and cloth flutter in Shots 2–3.

non_diegetic_music:
A low, solemn guqin and sparse percussion underscore at slow tempo, subdued and continuous without a swell.
```

## Prompt 02（对话行 L272）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 3>, a middle-aged warlord with a short dark beard in a dark robe, holding a worn map.
<Subject 2> is Guan Yu from <Picture 2>, a tall bearded warrior with a long dark beard, green robe and headscarf, standing behind Liu Bei's right side.
<Picture 1> is a storyboard reference for [Shot 1], a close-up of Liu Bei looking down at an old map marked at Xuzhou, Xudu, Hebei, and Jingzhou.
<Picture 2> is a storyboard reference for [Shot 2], defining Guan Yu approaching and standing at Liu Bei's right rear.
<Picture 3> is a storyboard reference for [Shot 3], a near shot of Liu Bei slowly folding the map.

summary:
[reference generation] The target video shows <Subject 1> studying a worn strategic map, <Subject 2> joining him with a quiet question, and <Subject 1> answering that they still lack someone who can tell him how to play the game of the realm.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - Liu Bei's identity, robe, and map-handling are retained.
<Subject 2> (appears in [Shot 2]): fully_preserved - Guan Yu's stature, long beard, green robe, and loyal posture are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - map close-up framing and worn marks stay aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - Guan Yu's approach and right-rear position stay aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - the near-shot map-folding beat stays aligned.

detailed_description:
The target video continues the same live-action cinematic Three Kingdoms style with dusk hillside light.
[Shot 1] A close-up matching <Picture 1> shows <Subject 1> looking down at an old paper map in his hands. Frayed marks remain at Xuzhou, Xudu, Hebei, and Jingzhou. His fingers lightly press the worn spots as wind stirs the paper edges.
[Shot 2] At 00:05.000, the shot cuts to a medium shot matching <Picture 2>: <Subject 2>, Guan Yu, walks slowly into frame and stops at <Subject 1>'s right rear. <Subject 2> (S2) turns slightly toward him and asks in a deep, steady male voice, <d>[Chinese] 兄长又在忧虑天下之事？</d> He closes his mouth and waits.
[Shot 3] At 00:10.000, the shot cuts to a near shot matching <Picture 3> as <Subject 1> slowly folds the map shut. <Subject 1> (S1) answers with restrained worry, <d>[Chinese] 我们有关、张、子龙，却始终少一个能告诉我……天下这盘棋，该如何走的人。</d> He finishes folding the map and holds it against his chest through the last frame.

overall_soundscape:
Soft hillside wind, paper rustle from the map, and quiet cloth movement when Guan Yu steps near.

non_diegetic_music:
Sparse guqin continues under the dialogue, still and unresolved.
```

## Prompt 03（对话行 L272）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 3>, seated indoors at night in a dark robe across a low wooden table.
<Subject 2> is Xu Shu from <Picture 1> and <Picture 2>, a scholarly adviser in plain robes, seated opposite Liu Bei.
<Subject 3> is the Xinye residence night interior from <Picture 1>, with oil-lamp light, wooden beams, and a low writing table.
<Picture 1> is a storyboard reference for [Shot 1], a wide night interior of Liu Bei and Xu Shu facing each other.
<Picture 2> is a storyboard reference for [Shot 2], a medium shot of Xu Shu looking at the realm map on the table.
<Picture 3> is a storyboard reference for [Shot 3], a close shot of Liu Bei silent and uneasy.

summary:
[reference generation] At night in <Subject 3>, <Subject 2> asks why <Subject 1> still wanders despite many fierce generals, and <Subject 1> admits that is exactly why he cannot rest.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - Liu Bei's seated posture, dark robe, and anxious restraint are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - Xu Shu's scholarly look, plain robes, and calm questioning manner are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - oil-lamp night interior and low wooden table are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - facing-seat wide framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - Xu Shu looking at the map stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - Liu Bei's silent close reaction stays aligned.

detailed_description:
The target video is live-action cinematic historical drama with warm flickering oil-lamp light and deep night shadows.
[Shot 1] A wide shot matching <Picture 1> establishes <Subject 3>, the Xinye residence at night. An oil lamp flickers on a low wooden table. <Subject 1> and <Subject 2> sit opposite each other across the table in quiet tension.
[Shot 2] At 00:04.000, the shot cuts to a medium shot matching <Picture 2> as <Subject 2> looks toward the realm map on the table. <Subject 2> (S1) asks evenly, <d>[Chinese] 主公麾下猛将如云，却为何多年仍四处辗转？</d> He keeps his eyes on the map after speaking.
[Shot 3] At 00:09.000, the shot cuts to a close-up matching <Picture 3> of <Subject 1>. He stays silent for a short beat, then answers quietly, <d>[Chinese] 正因如此，备才日夜难安。</d> The lamp light trembles across his face to the final frame.

overall_soundscape:
Quiet indoor night room tone, soft oil-lamp crackle, and distant cricket ambience outside.

non_diegetic_music:
Very low bamboo flute and soft string drones, intimate and tense.
```

## Prompt 04（对话行 L272）

```
subject_definitions:
<Subject 1> is Xu Shu from <Picture 1> and <Picture 2>, a scholarly adviser leaning forward and pointing at a realm map.
<Subject 2> is Liu Bei from <Picture 3>, listening intently across the table in the oil-lamp interior.
<Picture 1> is a storyboard reference for [Shot 1], Xu Shu leaning slightly forward in medium shot.
<Picture 2> is a storyboard reference for [Shot 2], a near shot of Xu Shu's finger on the realm map.
<Picture 3> is a storyboard reference for [Shot 3], a close-up of Liu Bei's focused gaze locking onto Xu Shu.

summary:
[reference generation] <Subject 1> explains that charging into battle needs fierce generals, but contending for the realm needs someone who can see ten years ahead; <Subject 2> immediately asks whether he already has a candidate.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Xu Shu's lean-in, map-pointing, and adviser presence are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - Liu Bei's sudden focused attention is retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - the forward-lean medium framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - finger-on-map near framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - Liu Bei's intent close-up stays aligned.

detailed_description:
The target video keeps the same night oil-lamp historical drama look.
[Shot 1] A medium shot matching <Picture 1> shows <Subject 1> leaning slightly forward. <Subject 1> (S1) says with measured emphasis, <d>[Chinese] 冲锋陷阵，可求猛将。</d> His expression stays earnest.
[Shot 2] At 00:05.000, the shot cuts to a near shot matching <Picture 2> as <Subject 1>'s finger presses a point on the realm map. <Subject 1> (S1) continues, <d>[Chinese] 可若想争天下，必须有人看得见十年之后。</d> The lamp flame flickers over the map paper.
[Shot 3] At 00:10.000, the shot cuts to a close-up matching <Picture 3> of <Subject 2>. His eyes snap fully onto Xu Shu. <Subject 2> (S2) asks urgently but controlled, <d>[Chinese] 先生心中，可有人选？</d> He holds the stare through the last frame.

overall_soundscape:
Indoor night room tone, oil-lamp crackle, and a soft paper scrape when the finger touches the map.

non_diegetic_music:
The flute motif thins and holds a single unresolved note under the question.
```

## Prompt 05（对话行 L272）

```
subject_definitions:
<Subject 1> is Xu Shu from <Picture 1> and <Picture 2>, speaking with solemn gravity about Zhuge Liang.
<Subject 2> is Liu Bei from <Picture 3>, softly repeating the name "Wolong / Zhuge Kongming."
<Picture 1> is a storyboard reference for [Shot 1], a near shot of Xu Shu speaking solemnly.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of Xu Shu pausing before naming Wolong.
<Picture 3> is a storyboard reference for [Shot 3], a near shot of Liu Bei repeating the name under his breath.

summary:
[reference generation] <Subject 1> names a man of Longzhong in Xiangyang, Zhuge Liang styled Kongming, known to the world as Wolong; <Subject 2> quietly repeats the name.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Xu Shu's solemn delivery and pause are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - Liu Bei's soft repetition and dawning recognition are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - solemn near framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - pause close-up stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - Liu Bei's whispered repetition framing stays aligned.

detailed_description:
The target video remains intimate night chamber drama under oil-lamp light.
[Shot 1] A near shot matching <Picture 1> holds on <Subject 1>. His face is solemn. <Subject 1> (S1) says carefully, <d>[Chinese] 襄阳隆中，有一人，复姓诸葛，名亮，字孔明。</d> He finishes the line without looking away.
[Shot 2] At 00:05.000, the shot cuts to a close-up matching <Picture 2>. <Subject 1> pauses, then continues with heavier weight, <d>[Chinese] 世人称他——卧龙。</d> The silence after the name is intentional.
[Shot 3] At 00:10.000, the shot cuts to a near shot matching <Picture 3> of <Subject 2>. <Subject 2> (S2) repeats under his breath, <d>[Chinese] 卧龙……诸葛孔明。</d> His eyes lower slightly as if memorizing the name through the final frame.

overall_soundscape:
Near-silent chamber tone with soft lamp crackle; dialogue sits dry and close.

non_diegetic_music:
A single deep guqin strike after "卧龙," then sustained quiet resonance.
```

## Prompt 06（对话行 L272）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 3>, first proposing a heavy gift invitation, then resolving to go himself.
<Subject 2> is Xu Shu from <Picture 2>, immediately rejecting the gift approach and insisting Liu Bei must visit in person.
<Picture 1> is a storyboard reference for [Shot 1], a medium shot of Liu Bei proposing to invite the sage with rich gifts.
<Picture 2> is a storyboard reference for [Shot 2], a near shot of Xu Shu shaking his head and refusing.
<Picture 3> is a storyboard reference for [Shot 3], a close-up of Liu Bei thinking, then lifting his head with resolve.

summary:
[reference generation] <Subject 1> offers to send rich gifts for the sage; <Subject 2> forbids it and says only a personal visit will do; <Subject 1> accepts and vows to go himself.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - Liu Bei's proposal and final resolve are retained.
<Subject 2> (appears in [Shot 2]): fully_preserved - Xu Shu's firm refusal and counsel are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - medium proposal framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - head-shake refusal framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - resolve close-up stays aligned.

detailed_description:
The target video closes the night counsel scene in the same cinematic oil-lamp style.
[Shot 1] A medium shot matching <Picture 1> shows <Subject 1> speaking with eager sincerity. <Subject 1> (S1) says, <d>[Chinese] 既是大贤，我便遣人重金相请。</d> He leans slightly forward as if ready to act at once.
[Shot 2] At 00:05.000, the shot cuts to a near shot matching <Picture 2>. <Subject 2> shakes his head immediately. <Subject 2> (S2) says firmly, <d>[Chinese] 不可。</d> After a short beat he continues, <d>[Chinese] 此人只能将军亲自去见。</d> His expression stays absolute.
[Shot 3] At 00:10.000, the shot cuts to a close-up matching <Picture 3> of <Subject 1>. He thinks for a moment, then lifts his head with clear resolve. <Subject 1> (S1) answers, <d>[Chinese] 好。</d> Then, with settled determination, <d>[Chinese] 备亲自去。</d> He holds the upward gaze through the final frame.

overall_soundscape:
Quiet chamber tone, soft lamp crackle, and a faint cloth rustle when Liu Bei lifts his head.

non_diegetic_music:
The score resolves into a firm low string hold under "备亲自去," then fades cleanly.
```

## Prompt 07（对话行 L274）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, a middle-aged warlord with a short dark beard in a dark traveling robe, leading the climb along a mountain stone path.
<Subject 2> is Guan Yu from <Picture 2>, a tall long-bearded warrior in green robes walking in the middle of the group.
<Subject 3> is Zhang Fei from <Picture 2> and <Picture 3>, a burly dark-bearded warrior in dark armor tones, impatient and loud.
<Subject 4> is the misty Longzhong mountain morning from <Picture 1>, with hidden peaks, a sea of green bamboo, and a winding blue-stone path.
<Picture 1> is a storyboard reference for [Shot 1], a wide misty bamboo-mountain establishing shot.
<Picture 2> is a storyboard reference for [Shot 2], the three brothers climbing the path with Liu Bei ahead.
<Picture 3> is a storyboard reference for [Shot 3], Zhang Fei catching up to argue and Liu Bei calming him.

summary:
[reference generation] On a misty Longzhong morning in <Subject 4>, <Subject 1>, <Subject 2>, and <Subject 3> climb a bamboo stone path; <Subject 3> complains that a great lord need not personally invite a rustic, and <Subject 1> firmly asks him to stop.

retention_analysis:
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - Liu Bei's lead position, mild firmness, and traveling robe are retained.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - Guan Yu's tall presence and watchful silence are retained.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - Zhang Fei's impatience, stride, and blunt gesture are retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - morning mist, bamboo sea, and winding blue-stone path are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - wide landscape framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - three-man climbing order stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - the confrontation near-framing stays aligned.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama with cool morning mist, soft diffused daylight, and lush green bamboo.
[Shot 1] A wide shot matching <Picture 1> opens on <Subject 4>: dawn mist over Longzhong peaks half-hidden in cloud, endless emerald bamboo, and a blue-stone path winding into depth. The camera trucks slowly left/right with small amplitude at slow speed. No people appear yet; only birds and a distant creek.
[Shot 2] At 00:04.000, the shot cuts to a full tracking shot matching <Picture 2>. <Subject 1> walks ahead on the stone path, <Subject 2> follows in the middle, and <Subject 3> brings up the rear. The camera tracks from behind and pushes in slowly as bamboo leaves rustle around them.
[Shot 3] At 00:09.000, the shot cuts to a medium shot matching <Picture 3>. <Subject 3> strides up beside <Subject 1>, right hand gesturing with impatience while <Subject 2> watches from behind. <Subject 3> (S1) blurts, <d>[Chinese] 哥哥！你如今是左将军、豫州牧，何等身份！为一个山野村夫，何必亲自来请？派个小校，绑也绑来了！</d> Without stopping, <Subject 1> turns his head, raises his right palm downward in a gentle pressing gesture, and answers firmly, <d>[Chinese] 贤者，不可以势召之，不可以力屈之。三弟，你若敬我，便收起这话。</d> The shot holds on their walking exchange to the final frame.

overall_soundscape:
Morning birdsong and distant creek water in Shot 1; stone-path footsteps and bamboo-leaf rustle in Shots 2–3.

non_diegetic_music:
Sparse guqin and soft flute at a walking tempo, calm and slightly solemn.
```

## Prompt 08（对话行 L274）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, arriving at the thatched cottage and bowing to the gate boy.
<Subject 2> is the twelve-or-thirteen-year-old boy servant from <Picture 3>, fair-featured, peeking from the half-open wooden gate.
<Subject 3> is the Longzhong thatched cottage valley from <Picture 1>, with a half-shut wooden gate, vine-covered fence, and a small pond in front.
<Picture 1> is a storyboard reference for [Shot 1], the bamboo clearing revealing the cottage, gate, vines, and pond.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of Liu Bei's hand knocking three times on the wooden gate.
<Picture 3> is a storyboard reference for [Shot 3], the boy opening the gate and Liu Bei announcing himself with a cupped-hand salute.

summary:
[reference generation] The bamboo opens onto <Subject 3>; <Subject 1> knocks at the gate, greets <Subject 2>, and asks to see Master Zhuge, but the boy says the master left early and is not home.

retention_analysis:
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - Liu Bei's respectful manner, robe, and cupped-hand salute are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - the young boy's fair features and naive gatekeeping are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - thatched cottage, half-open gate, vine fence, and front pond are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - valley cottage reveal stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - knocking-hand close-up stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - gate opening and salute exchange stay aligned.

detailed_description:
The target video continues the misty-morning Longzhong style with soft daylight and green bamboo.
[Shot 1] A wide-to-full shot matching <Picture 1> reveals <Subject 3> as the bamboo opens: a thatched cottage in the valley, wooden gate half shut, vines over the fence, and a quiet pond in front. The camera pushes in slowly with small amplitude. Wind moves bamboo and vines; no dialogue.
[Shot 2] At 00:05.000, the shot cuts to a close-up matching <Picture 2>: <Subject 1>'s hand hangs before the wooden gate, pauses, then knocks three times. Clear knocks sound: thud, thud, thud. The camera stays fixed.
[Shot 3] At 00:08.000, the shot cuts to a medium-near exchange matching <Picture 3>. The gate creaks open and <Subject 2>, a clear-eyed boy of about twelve or thirteen, looks up at <Subject 1>. <Subject 1> adjusts his collar, cups both hands, and bows. <Subject 1> (S1) says courteously, <d>[Chinese] 烦请通报，汉左将军刘备，求见诸葛先生。</d> <Subject 2> (S2) blinks, shakes his head, and replies simply, <d>[Chinese] 先生今日一早就外出了，不在家中。</d> The shot holds on the boy's innocent refusal to the final frame.

overall_soundscape:
Wind and bamboo rustle in Shot 1; three dry wooden knocks in Shot 2; a creaking gate hinge and quiet courtyard air in Shot 3.

non_diegetic_music:
The score thins to almost silence at the knock, then a soft unresolved flute under the boy's answer.
```

## Prompt 09（对话行 L274）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 3>, disappointed yet courteous, leaving a message and looking back at the cottage.
<Subject 2> is the gate boy from <Picture 1>, innocent and unsure about the master's return.
<Subject 3> is Zhang Fei from <Picture 2>, frowning with a clenched fist behind Liu Bei.
<Subject 4> is Guan Yu from <Picture 2>, calmly pressing a hand on Zhang Fei's shoulder to restrain him.
<Picture 1> is a storyboard reference for [Shot 1], the near exchange where Liu Bei asks when the master returns and the boy says there is no fixed schedule.
<Picture 2> is a storyboard reference for [Shot 2], Guan Yu restraining Zhang Fei's anger while Liu Bei bows and leaves a message.
<Picture 3> is a storyboard reference for [Shot 3], a distant view of the three departing as Liu Bei looks back toward the cottage.

summary:
[reference generation] <Subject 1> asks when the master will return; <Subject 2> says there is never a fixed date; <Subject 3> seethes while <Subject 4> restrains him; <Subject 1> bows, leaves word that he came, then looks back at the cottage as they leave.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - Liu Bei's courtesy, bow, and backward glance are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the boy's naive headshakes and clear speech are retained.
<Subject 3> (appears in [Shot 2]): fully_preserved - Zhang Fei's clenched frustration is retained.
<Subject 4> (appears in [Shot 2]): fully_preserved - Guan Yu's restraining hand on the shoulder is retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - the asking/answering near exchange stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - restraint and farewell bow stay aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - departure and look-back wide framing stay aligned.

detailed_description:
The target video keeps the same morning Longzhong cottage atmosphere with soft daylight.
[Shot 1] A near-shot dialogue exchange matching <Picture 1> holds on <Subject 1> and <Subject 2> at the gate. <Subject 1> steps forward, brow slightly furrowed, and leans in. <Subject 1> (S1) asks, <d>[Chinese] 小兄弟，可知先生何时回来？</d> <Subject 2> (S2) shakes his head with innocent frankness and answers, <d>[Chinese] 先生出游，从无定期。有时三五日，有时半月余。</d>
[Shot 2] At 00:06.000, the shot cuts to a medium shot matching <Picture 2>. Behind them, <Subject 3> locks his thick brows and clenches his right fist; <Subject 4> places a steady hand on <Subject 3>'s shoulder. In the foreground, <Subject 1> bows deeply to <Subject 2>, who steps aside. <Subject 1> (S1) says with composed courtesy, <d>[Chinese] 烦请转告先生——刘备，来过了。</d>
[Shot 3] At 00:11.000, the shot cuts to a wide distant shot matching <Picture 3>, framed from the cottage side: the three men walk away down the mountain path. After about ten steps, <Subject 1> stops and looks back toward the thatched cottage. Wind moves bamboo; no dialogue. The camera remains fixed through the final frame.

overall_soundscape:
Quiet courtyard air in Shot 1; soft cloth movement during the restraint and bow in Shot 2; mountain wind and bamboo rustle in Shot 3.

non_diegetic_music:
A low, lingering guqin phrase under the farewell, ending on an unfinished cadence as Liu Bei looks back.
```

## Prompt 10（对话行 L276）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2>, only his hand and sleeve visible as he knocks on the wooden gate.
<Subject 2> is the Longzhong thatched cottage valley from <Picture 1>, with a half-shut wooden gate, vine-covered fence, and a small pond in front.
<Picture 1> is a storyboard reference for [Shot 1], the bamboo clearing revealing the cottage, gate, vines, and pond.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of Liu Bei's hand knocking three times on the wooden gate.

summary:
[reference generation] The bamboo opens onto <Subject 2>; the camera slowly pushes toward the half-shut gate, then <Subject 1> pauses and knocks three times on the wooden door.

retention_analysis:
<Subject 1> (appears in [Shot 2]): fully_preserved - the respectful pause and three measured knocks of Liu Bei's hand are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - thatched cottage, half-open gate, vine fence, and front pond are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - valley cottage reveal stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - knocking-hand close-up stays aligned.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama with misty-morning Longzhong light, soft daylight, and green bamboo.
[Shot 1] A wide-to-full shot matching <Picture 1> reveals <Subject 2> as the bamboo opens: a thatched cottage in the valley, wooden gate half shut, vines over the fence, and a quiet pond in front. The camera pushes in slowly with small amplitude at slow speed. Wind moves bamboo and vines; no people speak; no dialogue.
[Shot 2] At 00:08.000, the shot cuts to a fixed close-up matching <Picture 2>: <Subject 1>'s hand hangs before the wooden gate, pauses briefly, then knocks three times. Clear wooden knocks sound in sequence: thud, thud, thud. The hand remains near the gate through the final frame. No dialogue.

overall_soundscape:
Wind and bamboo rustle throughout Shot 1; three dry wooden knocks and quiet courtyard air in Shot 2.

non_diegetic_music:
Sparse soft flute over the cottage reveal, thinning almost to silence at the knock.
```

## Prompt 11（对话行 L276）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 2>, standing before the thatched-cottage gate in a dark traveling robe, adjusting his collar and bowing with a cupped-hand salute.
<Subject 2> is the twelve-or-thirteen-year-old boy servant from <Picture 1> and <Picture 2>, fair-featured and clear-eyed, peeking from the half-open wooden gate.
<Subject 3> is the thatched-cottage gate entrance from <Picture 1>, with vine-covered fence and wooden gate opening onto the courtyard.
<Picture 1> is a storyboard reference for [Shot 1], the boy opening the gate and looking up at Liu Bei.
<Picture 2> is a storyboard reference for [Shot 2], Liu Bei saluting and the boy shaking his head to refuse.

summary:
[reference generation] At the gate of <Subject 3>, <Subject 2> opens the door; <Subject 1> announces himself as Han Left General Liu Bei seeking Master Zhuge; <Subject 2> says the master left early and is not home.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Liu Bei's respectful manner, robe, and cupped-hand salute are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the young boy's fair features and naive gatekeeping are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - wooden gate, vine fence, and cottage entrance are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - gate-opening medium framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - salute and refusal near exchange stays aligned.

detailed_description:
The target video continues the misty-morning Longzhong cottage style with soft daylight and green bamboo.
[Shot 1] A medium shot matching <Picture 1> begins as the wooden gate of <Subject 3> creaks open. <Subject 2>, a clear-eyed boy of about twelve or thirteen, peeks out and looks up at <Subject 1>. <Subject 1> adjusts his collar, cups both hands, and bows. <Subject 1> (S1) says courteously, <d>[Chinese] 烦请通报，汉左将军刘备，求见诸葛先生。</d>
[Shot 2] At 00:07.000, the shot cuts to a near exchange matching <Picture 2>, closer on <Subject 2> and <Subject 1>. <Subject 2> (S2) blinks, shakes his head, and replies simply, <d>[Chinese] 先生今日一早就外出了，不在家中。</d> The shot holds on the boy's innocent refusal through the final frame.

overall_soundscape:
A creaking gate hinge and quiet courtyard air throughout; dialogue sits clear and close with minimal ambience.

non_diegetic_music:
A soft unresolved flute under the boy's answer, ending without resolution.
```

## Prompt 12（对话行 L278）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 2>, disappointed yet courteous, standing before the cottage gate in a dark traveling robe.
<Subject 2> is the gate boy from <Picture 1> and <Picture 2>, innocent and unsure about the master's return, fair-featured and clear-eyed.
<Subject 3> is the thatched-cottage gate entrance from <Picture 1>, with vine-covered fence and wooden gate.
<Picture 1> is a storyboard reference for [Shot 1], Liu Bei leaning in to ask when the master will return.
<Picture 2> is a storyboard reference for [Shot 2], the boy shaking his head and saying there is no fixed schedule.

summary:
[reference generation] At the gate of <Subject 3>, <Subject 1> asks when Master Zhuge will return; <Subject 2> says the master never has a fixed date and may be gone for days or half a month.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Liu Bei's courtesy, slight frown, and forward lean are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the boy's naive headshakes and clear speech are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - wooden gate and vine fence entrance are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - the asking near-shot stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - the boy's answering near-shot stays aligned.

detailed_description:
The target video keeps the morning Longzhong cottage atmosphere with soft daylight and quiet courtyard air.
[Shot 1] A near shot matching <Picture 1> holds on <Subject 1> and <Subject 2> at the gate of <Subject 3>. <Subject 1> steps forward, brow slightly furrowed, and leans in. <Subject 1> (S1) asks, <d>[Chinese] 小兄弟，可知先生何时回来？</d>
[Shot 2] At 00:06.000, the shot cuts to a near shot matching <Picture 2>, closer on <Subject 2>. He shakes his head with innocent frankness and answers, <d>[Chinese] 先生出游，从无定期。有时三五日，有时半月余。</d> The shot holds on his naive expression through the final frame.

overall_soundscape:
Quiet courtyard air throughout; dialogue sits clear and close with minimal ambience.

non_diegetic_music:
A soft, unresolved flute under the boy's answer, ending without cadence.
```

## Prompt 13（对话行 L278）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 2>, courteous in farewell, bowing at the gate then looking back toward the cottage.
<Subject 2> is the gate boy from <Picture 1>, stepping aside as Liu Bei bows.
<Subject 3> is Zhang Fei from <Picture 1>, frowning with a clenched fist behind Liu Bei.
<Subject 4> is Guan Yu from <Picture 1>, calmly pressing a hand on Zhang Fei's shoulder to restrain him.
<Subject 5> is the Longzhong thatched cottage and mountain path from <Picture 2>, seen as the three men depart.
<Picture 1> is a storyboard reference for [Shot 1], Guan Yu restraining Zhang Fei while Liu Bei bows and leaves a message with the boy.
<Picture 2> is a storyboard reference for [Shot 2], a distant view of the three departing as Liu Bei looks back toward the cottage.

summary:
[reference generation] <Subject 3> seethes while <Subject 4> restrains him; <Subject 1> bows to <Subject 2>, leaves word that Liu Bei came, then walks away with the brothers and looks back at <Subject 5>.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Liu Bei's farewell bow and backward glance are retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - the boy stepping aside for the bow is retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - Zhang Fei's clenched frustration is retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - Guan Yu's restraining hand on the shoulder is retained.
<Subject 5> (appears in [Shot 2]): fully_preserved - cottage and departure path are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - restraint and farewell bow framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - departure and look-back wide framing stays aligned.

detailed_description:
The target video continues the morning Longzhong cottage atmosphere with soft daylight.
[Shot 1] A medium shot matching <Picture 1> shows, behind the gate, <Subject 3> locking his thick brows and clenching his right fist, while <Subject 4> places a steady hand on <Subject 3>'s shoulder. In the foreground, <Subject 1> bows deeply to <Subject 2>, who steps aside. <Subject 1> (S1) says with composed courtesy, <d>[Chinese] 烦请转告先生——刘备，来过了。</d>
[Shot 2] At 00:07.000, the shot cuts to a wide distant shot matching <Picture 2>, framed from the cottage side toward <Subject 5>: the three men walk away down the mountain path. After about ten steps, <Subject 1> stops and looks back toward the thatched cottage. Wind moves bamboo; no dialogue. The camera remains fixed through the final frame.

overall_soundscape:
Soft cloth movement during the restraint and bow in Shot 1; mountain wind and bamboo rustle in Shot 2.

non_diegetic_music:
A low, lingering guqin phrase under the farewell, ending on an unfinished cadence as Liu Bei looks back.
```

## Prompt 14（对话行 L300）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, a middle-aged warlord in a worn winter cloak, climbing the iced mountain path with firm steps.
<Subject 2> is Guan Yu from <Picture 2>, a tall long-bearded warrior in winter robes, walking behind Liu Bei.
<Subject 3> is Zhang Fei from <Picture 2> and <Picture 3>, a burly warrior hunched against the cold, exhaling white breath.
<Subject 4> is the midwinter Longzhong landscape from <Picture 1>, with leaden low clouds, snow-covered bamboo, and an iced stone path.
<Picture 1> is a storyboard reference for [Shot 1], a wide midwinter mountain shot with snow bamboo and icy path.
<Picture 2> is a storyboard reference for [Shot 2], the three brothers climbing again in winter.
<Picture 3> is a storyboard reference for [Shot 3], Zhang Fei complaining and Liu Bei turning to answer firmly.

summary:
[reference generation] In the bitter midwinter of <Subject 4>, <Subject 1>, <Subject 2>, and <Subject 3> climb the snowy path again; <Subject 3> urges turning back until spring, but <Subject 1> insists seeking a sage cannot stop for cold.

retention_analysis:
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - Liu Bei's worn cloak, firm gait, and gentle-but-unyielding gaze are retained.
<Subject 2> (appears in [Shot 2]): fully_preserved - Guan Yu's tall winter presence is retained.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - Zhang Fei's hunched cold posture, white breath, and impatient stamping are retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - leaden sky, snow bamboo, and iced stone path are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - winter wide landscape stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - three-man winter climb stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - complaint and reply framing stays aligned.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama in a bleak midwinter palette: leaden clouds, pale snow light, and sharp cold wind.
[Shot 1] A wide shot matching <Picture 1> opens on <Subject 4>: Longzhong peaks under low leaden cloud, bamboo seas coated in snow, and the stone path glazed with ice. The camera trucks slowly with small amplitude at slow speed. No dialogue; only howling wind.
[Shot 2] At 00:04.000, the shot cuts to a full tracking shot matching <Picture 2>. <Subject 1> leads in a worn winter cloak with firm steps, <Subject 2> follows, and <Subject 3> brings up the rear, shoulders hunched. White breath disperses in the cold air as they climb. The camera tracks from behind and pushes in slowly.
[Shot 3] At 00:08.000, the shot cuts to a medium shot matching <Picture 3>. <Subject 3> stamps his boot, shaking snow loose, and complains, <d>[Chinese] 哥哥！上次扑了个空，这次天寒地冻，那书生未必在家！</d> He continues, <d>[Chinese] 不如回去，等开春了再来！</d> <Subject 1> turns his head with a mild but uncompromising look and answers, <d>[Chinese] 求贤之道，如渴思饮，如饥思食。岂有因天冷便止步的道理？</d> The shot holds through the final frame.

overall_soundscape:
Howling winter wind throughout; crunching footsteps on iced stone and light snow-shake from Zhang Fei's stamping.

non_diegetic_music:
Sparse cold guqin over low drone, austere and wind-bitten.
```

## Prompt 15（对话行 L300）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, arriving again at the snowy thatched cottage and bowing to the gate boy.
<Subject 2> is the gate boy from <Picture 2>, surprised to see Liu Bei again.
<Subject 3> is Zhang Fei from <Picture 3>, erupting in anger behind Liu Bei.
<Subject 4> is Guan Yu from <Picture 3>, sharply stopping Zhang Fei.
<Subject 5> is the snow-covered thatched cottage yard from <Picture 1>, with uncleared snow on the fence and thin ice on the pond.
<Picture 1> is a storyboard reference for [Shot 1], the snowy cottage exterior with fence snow and iced pond.
<Picture 2> is a storyboard reference for [Shot 2], Liu Bei knocking, the boy opening, and their brief exchange.
<Picture 3> is a storyboard reference for [Shot 3], Zhang Fei's outburst, Guan Yu's rebuke, and Liu Bei raising a hand to wait.

summary:
[reference generation] At snowy <Subject 5>, <Subject 1> knocks again; <Subject 2> recognizes him and says Master Zhuge went drinking with Cui Zhouping and has not returned; <Subject 3> flares up, <Subject 4> stops him, and <Subject 1> says they will wait.

retention_analysis:
<Subject 1> (appears in [Shot 2], [Shot 3]): fully_preserved - Liu Bei's courtesy, salute, and restraining raised hand are retained.
<Subject 2> (appears in [Shot 2]): fully_preserved - the boy's surprised recognition is retained.
<Subject 3> (appears in [Shot 3]): fully_preserved - Zhang Fei's angry outburst is retained.
<Subject 4> (appears in [Shot 3]): fully_preserved - Guan Yu's sharp restraint is retained.
<Subject 5> (appears in [Shot 1]): fully_preserved - snowy fence, iced pond, and cottage yard are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - snowy yard framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - knock-and-exchange framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - anger and calming beat stay aligned.

detailed_description:
The target video continues the midwinter Longzhong cottage atmosphere with snow light and cold wind.
[Shot 1] A full shot matching <Picture 1> shows <Subject 5>: the thatched cottage yard with uncleared snow on the fence and thin ice over the pond. The three men approach. The camera pushes in slowly. No dialogue.
[Shot 2] At 00:04.000, the shot cuts to a medium shot matching <Picture 2>. <Subject 1> knocks again. The gate opens and <Subject 2> looks surprised. <Subject 2> (S2) says, <d>[Chinese] 又是刘将军？</d> <Subject 1> cups his hands and bows. <Subject 1> (S1) answers, <d>[Chinese] 正是刘备。诸葛先生今日可在？</d> <Subject 2> (S2) shakes his head: <d>[Chinese] 先生昨日被崔州平先生邀去饮酒论道，至今未归。</d>
[Shot 3] At 00:10.000, the shot cuts to a medium shot matching <Picture 3>. <Subject 3> (S3) bursts out, <d>[Chinese] 这分明是故意躲——</d> <Subject 4> (S4) cuts him off sharply, <d>[Chinese] 三弟！</d> <Subject 1> raises a hand to stop both, turns to the boy, and says calmly, <d>[Chinese] 无妨。我等在此等候便是。</d> The shot holds on his decision through the final frame.

overall_soundscape:
Cold wind and light snow crunch in Shot 1; wooden knocks and gate creak in Shot 2; tense cloth movement under the quarrel in Shot 3.

non_diegetic_music:
Cold sparse strings; a sharper accent under Zhang Fei's anger, then settling as Liu Bei decides to wait.
```

## Prompt 16（对话行 L300）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 2>, seated upright on the snowy stone steps beside the gate, motionless like a meditating monk as snow settles on his brows and shoulders.
<Subject 2> is Zhang Fei from <Picture 3>, pacing anxiously in the snowy yard.
<Subject 3> is Guan Yu from <Picture 3>, standing with arms folded and a complex gaze.
<Subject 4> is the snowy gate-side stone steps and cottage yard from <Picture 1>.
<Picture 1> is a storyboard reference for [Shot 1], Liu Bei brushing snow from the steps and sitting upright.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of snowflakes landing on Liu Bei's brows and shoulders while he remains still.
<Picture 3> is a storyboard reference for [Shot 3], Zhang Fei pacing and Guan Yu standing with folded arms.

summary:
[reference generation] At <Subject 4>, <Subject 1> brushes snow from the stone steps and sits upright in quiet endurance; snow falls on him without movement, while <Subject 2> paces in frustration and <Subject 3> watches with folded arms.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Liu Bei's upright seated endurance and snow-dusted stillness are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - Zhang Fei's restless pacing is retained.
<Subject 3> (appears in [Shot 3]): fully_preserved - Guan Yu's folded-arm stance and complex gaze are retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - snowy steps and gate-side yard are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - sitting-on-steps framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - snow-on-face close-up stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - pacing and watching framing stays aligned.

detailed_description:
The target video remains midwinter Longzhong drama with falling snow and cold soft daylight fading toward dusk.
[Shot 1] A full shot matching <Picture 1> shows <Subject 1> at <Subject 4>: he walks to the stone steps beside the wooden gate, brushes away snow with his hand, straightens his robe, and sits upright with composed dignity. No dialogue.
[Shot 2] At 00:05.000, the shot cuts to a close-up matching <Picture 2>. Snowflakes land on <Subject 1>'s brows and shoulders. He does not move, like an old monk in meditation. The camera stays fixed. No dialogue.
[Shot 3] At 00:10.000, the shot cuts to a medium-wide shot matching <Picture 3>. <Subject 2> paces in anxious circles, stomping snow. <Subject 3> stands with arms folded, eyes complex and silent. Wind drives finer snow across the yard through the final frame. No dialogue.

overall_soundscape:
Falling snow hush, soft wind, cloth and boot crunch from Zhang Fei's pacing; otherwise near silence around Liu Bei.

non_diegetic_music:
A single sustained guqin tone under the stillness, sparse and reverent.
```

## Prompt 17（对话行 L300）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, still seated through dusk, then rising to bow farewell and look back at the cottage.
<Subject 2> is Guan Yu and Zhang Fei as the two accompanying dark figures from <Picture 1>, waiting near Liu Bei in the snow.
<Subject 3> is the thatched cottage in the snowy dusk from <Picture 1> and <Picture 3>, with one brief indoor lamp that lights and goes out.
<Picture 1> is a storyboard reference for [Shot 1], a distant dusk view of three dark figures before the cottage in rising wind and snow.
<Picture 2> is a storyboard reference for [Shot 2], Liu Bei rising, brushing snow, and bowing toward the gate.
<Picture 3> is a storyboard reference for [Shot 3], the three walking into the blizzard as Liu Bei looks back at the lone cottage light.

summary:
[reference generation] In deepening dusk and heavier snow, <Subject 1> keeps waiting before <Subject 3> until a brief indoor lamp lights and dies; he then rises, bows farewell, and looks back at the cottage like a lone lamp in the snow night.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - upright waiting, farewell bow, and backward glance are retained.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - the two accompanying figures in snow are retained.
<Subject 3> (appears in [Shot 1], [Shot 3]): fully_preserved - snowy cottage and brief lamp flicker are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - distant three-dot dusk framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - rising-and-bowing medium framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - departure and look-back framing stays aligned.

detailed_description:
The target video closes the second visit in darker midwinter light as dusk falls and snowfall thickens.
[Shot 1] A distant wide shot matching <Picture 1> shows three dark figures shrinking before <Subject 3> in rising wind and snow. <Subject 1> remains seated on the steps with a straight spine. Inside the cottage, one lamp briefly lights, then goes out, as if the boy prepares an evening meal but no one invites them in. No dialogue.
[Shot 2] At 00:06.000, the shot cuts to a medium shot matching <Picture 2>. Snow falls harder. <Subject 1> slowly rises, brushes snow from his cloak, and bows deeply toward the gate. <Subject 1> (S1) says with restrained courtesy, <d>[Chinese] 刘备告辞。改日，再来。</d>
[Shot 3] At 00:10.000, the shot cuts to a medium-wide shot matching <Picture 3>. The three turn into the blizzard. After a few steps, <Subject 1> looks back: the thatched cottage in the snow night sits like a single lonely lamp. Wind and snow fill the final frame. No further dialogue.

overall_soundscape:
Louder blizzard wind and denser snowfall throughout; soft cloth brush when Liu Bei clears snow; muffled footsteps into the storm.

non_diegetic_music:
A low unfinished guqin cadence under the farewell, fading into wind as he looks back.
```

## Prompt 18（对话行 L314）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, thinner than before, eyes brighter, leading the third climb along the spring stone path.
<Subject 2> is Guan Yu from <Picture 2> and <Picture 3>, tall and long-bearded, restraining Zhang Fei with a low warning.
<Subject 3> is Zhang Fei from <Picture 2> and <Picture 3>, carrying a long serpent spear, furious and loud.
<Subject 4> is the early-spring Longzhong landscape from <Picture 1>, with melting ice, murmuring streams, budding willows, and first peach blossoms.
<Picture 1> is a storyboard reference for [Shot 1], a wide early-spring mountain path.
<Picture 2> is a storyboard reference for [Shot 2], Zhang Fei striding with his spear and slamming it into the ground.
<Picture 3> is a storyboard reference for [Shot 3], Liu Bei whirling in anger and Zhang Fei freezing back.

summary:
[reference generation] In early spring at <Subject 4>, the three brothers climb the stone path a third time; <Subject 3> threatens to burn the cottage if Zhuge is absent again, and <Subject 1> furiously forbids it while <Subject 2> tells him to be silent.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - thinner face, brighter eyes, and sudden fierce authority are retained.
<Subject 2> (appears in [Shot 2], [Shot 3]): fully_preserved - Guan Yu's tall presence and quiet restraint are retained.
<Subject 3> (appears in [Shot 2], [Shot 3]): fully_preserved - spear, fury, stamping halt, and startled retreat are retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - thawing ice, stream, willow buds, and peach blossoms are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - spring wide path stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - spear-slam full/medium framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - angry confrontation framing stays aligned.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama in fresh early-spring light: melting snow, clear stream water, and soft green.
[Shot 1] A wide shot matching <Picture 1> opens on <Subject 4>: Longzhong revives, ice thaws, a stream murmurs, willows bud, peach blossoms open. The three climb the blue-stone path a third time; <Subject 1> looks leaner, eyes brighter. The camera trucks slowly. No dialogue.
[Shot 2] At 00:05.000, the shot cuts to a full-to-medium shot matching <Picture 2>. <Subject 3> strides with his long serpent spear and slams it into the ground so the rock trembles. <Subject 3> (S1) shouts, <d>[Chinese] 哥哥！这诸葛村夫好大的架子！</d> He continues, <d>[Chinese] 前两次都不在家，这次若再不见，我一把火烧了这草庐，看他出不出来！</d>
[Shot 3] At 00:10.000, the shot cuts to a medium shot matching <Picture 3>. <Subject 1> whirls around, eyes blazing. <Subject 1> (S2) snaps, <d>[Chinese] 三弟！你若敢放肆，我刘备没有你这样的兄弟！</d> <Subject 3> freezes, never having seen him so angry, and steps back awkwardly. <Subject 2> (S3) says low, <d>[Chinese] 三弟，噤声。</d> The shot holds through the final frame.

overall_soundscape:
Spring stream murmur and light wind in Shot 1; spear-strike thud and tense footsteps in Shots 2–3.

non_diegetic_music:
Bright sparse guqin turning sharper under Liu Bei's anger.
```

## Prompt 19（对话行 L314）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, adjusting his robe and knocking at the cottage gate a third time.
<Subject 2> is the gate boy from <Picture 3>, eyes brightening at Liu Bei's return.
<Subject 3> is the thatched cottage from <Picture 1>, gate half ajar, new green on the fence, old plum in full bloom with floating fragrance.
<Picture 1> is a storyboard reference for [Shot 1], a wide-to-full reveal of the spring cottage, plum blossoms, and half-open gate.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of Liu Bei's hand knocking the wooden gate a third time.
<Picture 3> is a storyboard reference for [Shot 3], the boy opening the gate and telling Liu Bei the master is home napping.

summary:
[reference generation] At blossoming <Subject 3>, <Subject 1> knocks a third time; <Subject 2> greets him and says Master Zhuge is home, napping in the thatched hall.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - careful dress adjustment, third knock, and earnest smile are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - the boy's bright recognition and nod are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - half-open gate, new fence green, and blooming plum are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - spring cottage reveal stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - third-knock close-up stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - gate exchange framing stays aligned.

detailed_description:
The target video continues early-spring Longzhong light with plum fragrance and soft green.
[Shot 1] A wide-to-full shot matching <Picture 1> reveals <Subject 3>: the cottage unchanged, gate half ajar, new green on the fence, old plum in full bloom with floating fragrance. <Subject 1> adjusts his collar, draws a deep breath, and walks forward slowly. No dialogue.
[Shot 2] At 00:05.000, the shot cuts to a close-up matching <Picture 2>: <Subject 1>'s hand knocks the wooden gate a third time. Three clear knocks. No dialogue.
[Shot 3] At 00:08.000, the shot cuts to a medium shot matching <Picture 3>. The gate opens; <Subject 2>'s eyes brighten. <Subject 2> (S1) says, <d>[Chinese] 刘将军！您怎么又来了？</d> <Subject 1> (S2) smiles earnestly, <d>[Chinese] 小兄弟，诸葛先生今日可在？</d> <Subject 2> glances back, nods, and answers, <d>[Chinese] 先生在的。正在草堂午睡。</d> The shot holds through the final frame.

overall_soundscape:
Soft spring wind and faint plum-branch rustle; three wooden knocks; quiet courtyard air under the dialogue.

non_diegetic_music:
Gentle rising guqin, warmer than winter cues, unresolved into hope.
```

## Prompt 20（对话行 L314）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 2>, whispering not to disturb the master, then standing motionless below the thatched-hall steps as plum petals fall on his shoulder.
<Subject 2> is Zhang Fei from <Picture 3>, fretting outside the fence, ears and cheeks rubbed in impatience.
<Subject 3> is Guan Yu from <Picture 3>, firmly holding Zhang Fei back outside the fence.
<Subject 4> is the thatched-hall courtyard from <Picture 1>, with west-slanting sun and blooming plum.
<Picture 1> is a storyboard reference for [Shot 1], Liu Bei entering quietly and standing below the hall steps.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of Liu Bei standing still as plum petals land on his shoulder.
<Picture 3> is a storyboard reference for [Shot 3], Zhang Fei fretting outside while Guan Yu holds him down.

summary:
[reference generation] <Subject 1> tells the boy not to wake the master, leaves <Subject 2> and <Subject 3> outside, and waits motionless below the hall steps of <Subject 4> while plum petals fall on him.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - hushed courtesy and unblinking endurance are retained.
<Subject 2> (appears in [Shot 3]): fully_preserved - Zhang Fei's anxious fretting is retained.
<Subject 3> (appears in [Shot 3]): fully_preserved - Guan Yu's firm hold is retained.
<Subject 4> (appears in [Shot 1]): fully_preserved - courtyard, steps, and plum are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - quiet entry and waiting framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - petal-on-shoulder close-up stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - outside restraint framing stays aligned.

detailed_description:
The target video keeps early-spring courtyard light as the sun slides west.
[Shot 1] A full shot matching <Picture 1> shows <Subject 1> at <Subject 4>. Delight flashes, then he lowers his voice. <Subject 1> (S1) says, <d>[Chinese] 切勿惊扰先生。我等在此等候。</d> He signals Guan Yu and Zhang Fei to wait outside, then steps softly into the yard and stands below the thatched-hall steps with hands at his sides.
[Shot 2] At 00:06.000, the shot cuts to a close-up matching <Picture 2>. Afternoon light slants. <Subject 1> stands without blinking. A breeze passes; plum petals settle on his shoulder. He does not move. No dialogue.
[Shot 3] At 00:11.000, the shot cuts to a medium shot matching <Picture 3> outside the fence: <Subject 2> frets and scratches in impatience while <Subject 3> holds him down hard. No dialogue. The shot holds through the final frame.

overall_soundscape:
Hushed courtyard air, soft footsteps, light plum-petal rustle; muted struggle sounds outside the fence.

non_diegetic_music:
A single sustained respectful tone under Liu Bei's stillness.
```

## Prompt 21（对话行 L314）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 2> and <Picture 3>, waiting below the steps, then stepping forward with reddened eyes to grasp Zhuge Liang's arms.
<Subject 2> is Zhuge Liang from <Picture 1> and <Picture 2>, a tall young scholar about eight chi in height, jade-like face, silk headscarf, crane cloak, ethereal bearing.
<Subject 3> is the thatched-hall doorway from <Picture 1>, with a lifted curtain.
<Picture 1> is a storyboard reference for [Shot 1], Zhuge Liang stepping out through the curtain in crane cloak.
<Picture 2> is a storyboard reference for [Shot 2], Zhuge Liang bowing and Liu Bei hurrying forward to support his arms.
<Picture 3> is a storyboard reference for [Shot 3], a near shot of Liu Bei speaking with emotion and reddened eyes.

summary:
[reference generation] After a long wait, <Subject 2> emerges from <Subject 3>; he apologizes for not knowing <Subject 1> stood below, and <Subject 1> greets him with long-sought emotion.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - waiting posture, hurried advance, and reddened eyes are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - height, jade face, silk scarf, crane cloak, and ethereal presence are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - curtain doorway is retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - first appearance framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - bow and arm-support framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - emotional near-shot stays aligned.

detailed_description:
The target video remains early-spring courtyard drama with soft afternoon light.
[Shot 1] A medium shot matching <Picture 1> begins after a long wait. A light cough sounds inside. The curtain of <Subject 3> lifts, and <Subject 2> steps out slowly: tall, jade-like face, silk headscarf, crane cloak, ethereal as an immortal. He sees <Subject 1> standing below and is briefly startled.
[Shot 2] At 00:06.000, the shot cuts to a medium-near shot matching <Picture 2>. <Subject 2> bows long. <Subject 2> (S1) says, <d>[Chinese] 将军久立阶下，亮竟不知，实在失礼。</d> <Subject 1> hurries forward and supports both of <Subject 2>'s arms with both hands, eyes reddening.
[Shot 3] At 00:10.000, the shot cuts to a near shot matching <Picture 3> on <Subject 1>. <Subject 1> (S2) says with trembling gratitude, <d>[Chinese] 备久慕先生大名，前两次无缘得见。今日得见先生，备之幸也！</d> The shot holds through the final frame.

overall_soundscape:
Quiet courtyard air, soft curtain rustle, light cloth movement as they meet.

non_diegetic_music:
A warm resolving guqin phrase as Wolong appears, then a tender hold under Liu Bei's greeting.
```

## Prompt 22（对话行 L314）

```
subject_definitions:
<Subject 1> is Zhuge Liang from <Picture 2>, seated across a low table, calmly pointing at the northern part of a realm map.
<Subject 2> is Liu Bei from <Picture 1> and <Picture 3>, seated opposite Zhuge Liang, listening with grave attention.
<Subject 3> is the austere thatched hall from <Picture 1>, with one table, one qin, and several bamboo scrolls; Guan Yu and Zhang Fei stand solemnly outside the doorway.
<Picture 1> is a storyboard reference for [Shot 1], Liu Bei and Zhuge Liang seated across the table with the realm map opened.
<Picture 2> is a storyboard reference for [Shot 2], a near shot of Zhuge Liang pointing north on the map while explaining Cao Cao.
<Picture 3> is a storyboard reference for [Shot 3], Liu Bei nodding with a grave expression.

summary:
[reference generation] Inside austere <Subject 3>, <Subject 1> explains that Cao Cao defeated Yuan Shao by planning as well as timing, and now commands a million men with the emperor, so he must not be contested head-on; <Subject 2> nods gravely.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - calm scholarly bearing and map-pointing are retained.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - attentive seated listening and grave nod are retained.
<Subject 3> (appears in [Shot 1]): fully_preserved - sparse hall, table, qin, scrolls, and map are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - facing-seat hall framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - map-lecture near framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - Liu Bei's grave reaction stays aligned.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama in a dim, austere thatched hall with soft daylight through the doorway.
[Shot 1] A medium shot matching <Picture 1> establishes <Subject 3>: one table, one qin, several bamboo scrolls. <Subject 2> and <Subject 1> sit opposite across the table; Guan Yu and Zhang Fei stand solemnly outside. The realm map is opened again on the table. No dialogue yet.
[Shot 2] At 00:04.000, the shot cuts to a near shot matching <Picture 2>. <Subject 1> points to the north of the map. <Subject 1> (S1) says steadily, <d>[Chinese] 自董卓以来，豪杰并起。曹操比于袁绍，名微而众寡，然操遂能克绍，以弱为强者——</d> He looks up at Liu Bei: <d>[Chinese] 非惟天时，抑亦人谋也。</d> His finger traces the Central Plains: <d>[Chinese] 今操已拥百万之众，挟天子而令诸侯，此诚不可与争锋。</d>
[Shot 3] At 00:12.000, the shot cuts to a near shot matching <Picture 3> of <Subject 2> nodding with a grave face. No dialogue. The shot holds through the final frame.

overall_soundscape:
Quiet indoor hall tone; soft fingertip on paper map; muted outdoor courtyard air beyond the doorway.

non_diegetic_music:
Low restrained strings under the strategic speech.
```

## Prompt 23（对话行 L314）

```
subject_definitions:
<Subject 1> is Zhuge Liang from <Picture 1> and <Picture 2>, shifting his finger from Jiangdong to Jingxiang and Yizhou on the realm map.
<Subject 2> is Liu Bei from <Picture 1> and <Picture 3>, leaning forward to ask what he should do, then listening intently.
<Picture 1> is a storyboard reference for [Shot 1], Zhuge Liang pointing to Jiangdong while Liu Bei leans in.
<Picture 2> is a storyboard reference for [Shot 2], Zhuge Liang pointing from Jingzhou to Yizhou.
<Picture 3> is a storyboard reference for [Shot 3], a near shot of Zhuge Liang's burning gaze as he names crossing Jing and Yi.

summary:
[reference generation] <Subject 1> says Sun Quan can be an ally but not a target, then points from Jingzhou to Yizhou as the true base for <Subject 2>, who asks what he should do and listens with rising urgency.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - map-hand movement and piercing gaze are retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - forward lean and urgent question are retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - Jiangdong counsel framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - Jing-Yi pointing framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - burning-gaze near shot stays aligned.

detailed_description:
The target video continues the austere thatched-hall counsel with the opened realm map.
[Shot 1] A medium-to-near shot matching <Picture 1> shows <Subject 1> moving his finger to Jiangdong. <Subject 1> (S1) says, <d>[Chinese] 孙权据有江东，已历三世，国险而民附，贤能为之用。</d> He pauses: <d>[Chinese] 此可以为援，而不可图也。</d> <Subject 2> leans forward. <Subject 2> (S2) asks, <d>[Chinese] 那……备该当如何？</d>
[Shot 2] At 00:07.000, the shot cuts to a near shot matching <Picture 2>. <Subject 1>'s finger falls on Jingxiang, then moves to Bashu. <Subject 1> (S1) says, <d>[Chinese] 荆州北据汉、沔，利尽南海，东连吴会，西通巴蜀，此用武之国，而其主不能守。</d> He taps Yizhou lightly: <d>[Chinese] 益州险塞，沃野千里，天府之土，高祖因之以成帝业。</d>
[Shot 3] At 00:12.000, the shot cuts to a close near shot matching <Picture 3>. His gaze burns. <Subject 1> (S1) continues, <d>[Chinese] 将军既帝室之胄，信义著于四海，若跨有荆、益——</d> The line hangs unfinished into the final frame.

overall_soundscape:
Quiet hall tone and soft map-paper friction under the pointing finger.

non_diegetic_music:
Tension rises under the Jing-Yi counsel, held open at the unfinished line.
```

## Prompt 24（对话行 L314）

```
subject_definitions:
<Subject 1> is Zhuge Liang from <Picture 1> and <Picture 2>, standing and drawing two campaign lines across the realm map.
<Subject 2> is Liu Bei from <Picture 1>, seated and listening as the plan unfolds.
<Picture 1> is a storyboard reference for [Shot 1], Zhuge Liang standing and tracing two lines on the map.
<Picture 2> is a storyboard reference for [Shot 2], a close-up of Zhuge Liang's eyes lit as if by spreading wildfire.
<Picture 3> is a storyboard reference for [Shot 3], a near shot as he delivers the final line about the people welcoming the army.

summary:
[reference generation] <Subject 1> stands and maps a two-route northern campaign—ally with Sun Quan, then strike from Jingzhou and Yizhou when the realm shifts—while <Subject 2> listens in silence.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - standing map gesture and fiery eyes are retained.
<Subject 2> (appears in [Shot 1]): fully_preserved - seated absorbing silence is retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - standing two-line gesture stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - fiery-eye close-up stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - final-line near framing stays aligned.

detailed_description:
The target video stays in the thatched hall with intensifying strategic urgency.
[Shot 1] A medium shot matching <Picture 1> shows <Subject 1> rising and drawing two lines across the map. <Subject 1> (S1) says, <d>[Chinese] 保其岩阻，西和诸戎，南抚夷越，外结好孙权，内修政理。</d> He looks at <Subject 2> and continues, word by word, <d>[Chinese] 天下有变，则命一上将将荆州之军以向宛、洛，将军身率益州之众出于秦川——</d>
[Shot 2] At 00:09.000, the shot cuts to a close-up matching <Picture 2> of <Subject 1>'s eyes, lit as if wildfire were spreading.
[Shot 3] At 00:11.000, the shot cuts to a near shot matching <Picture 3>. <Subject 1> (S1) finishes, <d>[Chinese] 百姓孰敢不箪食壶浆以迎将军者乎？</d> The shot holds on his conviction through the final frame.

overall_soundscape:
Quiet hall tone; firmer fingertip strokes as the two campaign lines are drawn.

non_diegetic_music:
A swelling low martial drone under the northern plan, peaking on the final question.
```

## Prompt 25（对话行 L314）

```
subject_definitions:
<Subject 1> is Liu Bei from <Picture 1> and <Picture 2>, stunned into silence, then rising to bow deeply to Zhuge Liang with a trembling voice.
<Subject 2> is Zhuge Liang from <Picture 1>, seated receiving Liu Bei's bow.
<Picture 1> is a storyboard reference for [Shot 1], Liu Bei sitting stunned after the counsel.
<Picture 2> is a storyboard reference for [Shot 2], Liu Bei rising and bowing deeply.
<Picture 3> is a storyboard reference for [Shot 3], a near shot of Liu Bei speaking with a trembling voice.

summary:
[reference generation] After the Longzhong counsel, <Subject 1> sits stunned, then rises and bows to <Subject 2>, declaring the strategy has cleared the clouds from his eyes.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - stunned silence, deep bow, and trembling gratitude are retained.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - calm receiving presence is retained.
<Picture 1> ([Shot 1] composition anchor): fully_preserved - stunned seated framing stays aligned.
<Picture 2> ([Shot 2] composition anchor): fully_preserved - rising-and-bowing framing stays aligned.
<Picture 3> ([Shot 3] composition anchor): fully_preserved - trembling-speech near shot stays aligned.

detailed_description:
The target video closes the Longzhong counsel in the same austere hall light.
[Shot 1] A near shot matching <Picture 1> holds on <Subject 1> sitting stunned for a long beat after the speech. Dust motes hang in the quiet. No dialogue.
[Shot 2] At 00:05.000, the shot cuts to a medium shot matching <Picture 2>. <Subject 1> suddenly rises and bows deeply to <Subject 2>. <Subject 1> (S1) says, <d>[Chinese] 先生之言，如拨云见日，使备茅塞顿开！</d>
[Shot 3] At 00:10.000, the shot cuts to a near shot matching <Picture 3>. His voice trembles. <Subject 1> (S1) continues, <d>[Chinese] 备蹉跎半生，今日方知天下大势！</d> The shot holds through the final frame.

overall_soundscape:
Deep hall silence in Shot 1; soft robe movement and bowing cloth sound in Shots 2–3.

non_diegetic_music:
A clear resolving guqin cadence under the bow, warm and conclusive.
```

## Prompt 26（对话行 L318）

```
subject_definitions:
<Subject 1> is Liu Bei whose identity, face, beard, hairstyle, clothing, and body type come only from <Picture 2>. <Picture 2> defines character appearance only and must not define any background, architecture, or environment.
<Subject 2> is the young page boy whose identity, face, hairstyle, clothing, and body type come only from <Picture 3>. <Picture 3> defines character appearance only and must not define any background, architecture, or environment.
<Subject 3> is the complete Longzhong thatched-cottage environment taken only from <Picture 1>: the cottage, fence, outer courtyard gate, the existing outside road, early-spring light, and the spatial layout of road → outer gate → courtyard → cottage. All background and location must come from <Picture 1> only.
<Picture 1> is the sole scene and composition reference for the whole video. Even if the gate appears open or ajar in <Picture 1>, the target video must reconstruct that outer courtyard gate as fully closed from the first frame until after Liu Bei knocks.
<Picture 2> is an identity-only character reference for <Subject 1> and must never be used as a background or location source.
<Picture 3> is an identity-only character reference for <Subject 2> and must never be used as a background or location source.

summary:
[reference generation] In the early-spring cottage setting of <Subject 3> from <Picture 1>, <Subject 1> walks along the existing outside road toward the fully closed outer courtyard gate, knocks three times while still outside, then waits; only afterward does <Subject 2> open the gate from inside, and the two face each other for a brief greeting about Master Zhuge napping in the thatched hall.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - face, beard, hair, robe, and body type from <Picture 2> are retained; he remains outside the courtyard the entire time.
<Subject 2> (appears only in [Shot 3]): fully_preserved - face, hair, clothing, and body type from <Picture 3> are retained; he appears only after the knock, opening the gate from inside.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - cottage, fence, outer gate, existing outside road, early-spring light, and road→gate→yard→cottage layout from <Picture 1> are retained without relocating architecture.
<Picture 1> (whole-video scene anchor): fully_preserved - sole background source; the outer gate is force-closed from frame one despite any open-gate appearance in the reference.
<Picture 2> (identity only): fully_preserved - used only for Liu Bei appearance, never as background.
<Picture 3> (identity only): fully_preserved - used only for the page boy's appearance, never as background.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama in early-spring light, using only the cottage environment of <Subject 3> from <Picture 1>.
[Shot 1] A wide establishing shot opens on <Subject 3> from <Picture 1>: the thatched cottage, fence, outer courtyard gate, and the existing outside road. Critical: from the first frame, the outer courtyard gate is fully closed—tight shut, no gap, no slit, no half-open state—even if <Picture 1> originally shows it open. <Subject 1>, appearance from <Picture 2>, is already on the existing outside road and walking toward the cottage and closed outer gate; he is not standing at the door yet. He faces the cottage with restrained expectation and, while approaching, lightly adjusts collar, cuffs, and robe for neatness. He stays strictly on the reference road already present in <Picture 1>—no new path, no fork, no crossing snow or grass at random, no entering the courtyard, no detour. He stops directly in front of the still fully closed outer courtyard gate. No dialogue. No page boy yet.
[Shot 2] At 00:06.000, the shot cuts closer while preserving the same spatial relation: outside road → closed outer gate → courtyard → cottage. <Subject 1> remains outside the yard, facing the still fully closed outer courtyard gate—not an inner door by the cottage, and not a second invented door. He raises his hand and knocks three clear, polite times. After the third knock, he lowers his hand and waits quietly outside. The gate remains closed until the end of this shot. No dialogue. The page boy has not appeared.
[Shot 3] At 00:09.000, after about one second of pause, the previously fully closed outer courtyard gate opens slowly from inside for the first time. <Subject 2>, appearance from <Picture 3>, comes from inside the courtyard to the gate and opens it. Background remains the same <Subject 3> cottage yard from <Picture 1>. After the gate opens, <Subject 1> turns to face <Subject 2> directly—eyes, body, and face oriented to the boy, not stuck facing the wooden door panel or looking aside. <Subject 2> (S1) brightens with recognition and slight surprise, <d>[Chinese] 刘将军！您怎么又来了？</d> <Subject 1> (S2), facing the boy with a mild sincere smile, asks courteously, <d>[Chinese] 小兄弟，诸葛先生今日可在？</d> <Subject 2> glances back toward the cottage inside the yard, then turns back to Liu Bei, nods, and says, <d>[Chinese] 先生在的。正在草堂午睡。</d> <Subject 1> keeps facing him and listening; his expression shifts from restrained expectation to mild relief and renewed hope. No Zhuge Liang, Guan Yu, Zhang Fei, or other servants appear.

overall_soundscape:
Soft early-spring outdoor air and light wind around the cottage yard; clear wooden knocks in Shot 2; a slow gate-opening creak in Shot 3; quiet courtyard tone under the dialogue.

non_diegetic_music:
Sparse warm guqin under the approach, thinning nearly to silence at the knocks, then a soft unresolved hold under the boy's answer.

硬性约束（已写入上文，生成时必须遵守）:
- 首帧：刘备在院外既有道路上走向草庐；院门完全关闭；无门缝；书童未出现。
- 敲门前院门始终关严；敲门后才第一次从内打开。
- 敲的是院子最外侧院门；刘备始终在院外。
- 开门后刘备必须正面面向书童对话。
- 背景只来自草庐远景；人物三视图只定人不定景。
```

## Prompt 27（对话行 L329）

```
subject_definitions:
<Subject 1> is Liu Bei whose identity, face, beard, hairstyle, clothing, and body type come only from <Picture 1>. <Picture 1> defines character appearance only and must not define any background, architecture, or environment.
<Subject 2> is Guan Yu whose identity, face, long beard, hairstyle, clothing, and body type come only from <Picture 2>. <Picture 2> defines character appearance only and must not define any background, architecture, or environment.
<Subject 3> is Zhang Fei whose identity, face, beard, hairstyle, clothing, and body type come only from <Picture 3>. <Picture 3> defines character appearance only and must not define any background, architecture, or environment.
<Subject 4> is the young page boy already present at the opened outer courtyard gate, continuing from the previous beat; he appears only briefly in [Shot 1] and does not enter the later interior wait.
<Subject 5> is the cottage exterior environment taken only from <Picture 4>: the outer courtyard gate, fence, outside space, and the outside waiting position. All exterior background, architecture, light, and spatial relation for outside shots must come from <Picture 4> only.
<Subject 6> is the inner courtyard environment taken only from <Picture 5>: the thatched-hall steps, stone paving, plum tree, and Liu Bei's waiting position at the foot of the steps. All interior background, architecture, light, and spatial relation for the courtyard wait must come from <Picture 5> only.
<Picture 4> is the sole exterior scene and composition reference for [Shot 1] and [Shot 3], defining the outer gate, fence, outside waiting space, and the spatial relation that Guan Yu and Zhang Fei remain outside the yard.
<Picture 5> is the sole interior scene and composition reference for [Shot 2], defining the thatched-hall steps, courtyard paving, plum tree, and where Liu Bei stands waiting alone at the foot of the steps.
<Picture 1>, <Picture 2>, and <Picture 3> are identity-only character references and must never be used as background or location sources.

summary:
[reference generation] Continuing after the page boy has opened the gate, <Subject 1> quietly tells <Subject 4> not to disturb the master and signals <Subject 2> and <Subject 3> to stay outside in the exterior space of <Subject 5> from <Picture 4>; then <Subject 1> alone enters the inner courtyard of <Subject 6> from <Picture 5>, stands still at the foot of the thatched-hall steps as plum petals fall on his shoulder, while outside <Subject 3> grows restless and <Subject 2> firmly restrains him from entering.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - face, beard, hair, robe, and body type from <Picture 1> are retained; he alone enters the yard and waits at the foot of the steps.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - face, long beard, hair, clothing, and body type from <Picture 2> are retained; he remains outside the gate/fence at all times and never enters the courtyard.
<Subject 3> (appears in [Shot 1], [Shot 3]): fully_preserved - face, beard, hair, clothing, and body type from <Picture 3> are retained; he remains outside the gate/fence at all times and never enters the courtyard.
<Subject 4> (appears in [Shot 1] only): partially_preserved - present only for the quiet exchange at the opened gate, then drops out of later shots.
<Subject 5> (appears in [Shot 1], [Shot 3]): fully_preserved - outer gate, fence, exterior space, and outside waiting position from <Picture 4> are retained without relocating architecture.
<Subject 6> (appears in [Shot 2] only): fully_preserved - thatched-hall steps, stone paving, plum tree, light, and waiting position from <Picture 5> are retained; no new interior path is invented.
<Picture 4> (exterior composition for [Shot 1], [Shot 3]): fully_preserved - sole exterior background source.
<Picture 5> (interior composition for [Shot 2]): fully_preserved - sole interior background source.
<Picture 1>, <Picture 2>, <Picture 3> (identity only): fully_preserved - used only for character appearance, never as background.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama, continuing directly after the previous beat in which the page boy has already opened the outer courtyard gate. Character appearances come only from their identity references; all backgrounds come only from the two scene references.
[Shot 1] At the opened outer courtyard gate in the exterior space of <Subject 5> from <Picture 4>, <Subject 1> stands just outside the gateway with a respectful, restrained expression after the prior exchange. <Subject 4> remains at the gate. Softly, lightly, and with deference, <Subject 1> (S1) says, <d>[Chinese] 切勿惊扰先生。我等在此等候。</d> He then turns and signals <Subject 2> and <Subject 3> to stay outside and not enter the yard. <Subject 2> and <Subject 3> halt outside the outer gate / beyond the fence in the waiting position defined by <Picture 4>; they do not step into the courtyard. After the signal, <Subject 1> alone walks lightly through the open gate into the yard. Camera stays with the exterior spatial relation of <Picture 4>: outside waiting space → outer gate → courtyard beyond. Guan Yu and Zhang Fei remain outside.
[Shot 2] At 00:05.500, cut into the interior courtyard of <Subject 6> from <Picture 5>. <Subject 1> is already inside and walks slowly to the foot of the thatched-hall steps. He stops directly below the steps—not at the outer gate, not midway on a new invented path—body upright, hands hanging naturally or resting quietly before him, waiting in silence. Afternoon light leans slightly westward; the yard is quiet; the plum tree stirs gently. A light breeze passes and a few plum petals drift down onto his shoulder. He does not move, does not brush the petals away, does not look around, and does not speak. Extreme patience and respect. Critical: only <Subject 1> is inside; <Subject 2> and <Subject 3> must not appear in the interior background.
[Shot 3] At 00:10.000, cut back outside the outer gate / beyond the fence in the exterior space of <Subject 5> from <Picture 4>, preserving that outside waiting layout. <Subject 3> grows clearly impatient—shifting, rubbing an ear, rubbing his face, stamping lightly, or twisting restlessly—but does not shout. Beside him, <Subject 2> stays steady and restrained, firmly blocking <Subject 3> from rushing into the yard; the hold is firm but not exaggerated. Zhang Fei wants to move; Guan Yu holds him down. Neither man enters the courtyard. No dialogue.

overall_soundscape:
Quiet early-afternoon courtyard air after the gate is open; Liu Bei's low respectful voice in Shot 1; soft footfalls as he alone enters; faint breeze and a near-silent petal fall in Shot 2; outside, restless cloth and boot scuffs from Zhang Fei with Guan Yu's firm restraining movement, without shouting.

non_diegetic_music:
Sparse restrained guqin under the quiet instruction, almost still during Liu Bei's silent wait under falling petals, then a tighter tense hold under Zhang Fei's impatience outside.
```

## Prompt 28（对话行 L332）

```
subject_definitions:
<Subject 1> is Liu Bei whose identity, face, beard, hairstyle, clothing, and body type come only from <Picture 1>. <Picture 1> defines character appearance only and must not define any background, architecture, or environment.
<Subject 2> is Guan Yu whose identity, face, long beard, hairstyle, clothing, and body type come only from <Picture 2>. <Picture 2> defines character appearance only and must not define any background, architecture, or environment.
<Subject 3> is Zhang Fei whose identity, face, beard, hairstyle, clothing, and body type come only from <Picture 3>. <Picture 3> defines character appearance only and must not define any background, architecture, or environment.
<Subject 4> is the young page boy already present at the opened outer courtyard gate, continuing from the previous beat; he appears only briefly in [Shot 1] and does not enter the later interior wait.
<Subject 5> is the cottage exterior environment taken only from <Picture 4>: the outer courtyard gate, fence, outside space, and the outside waiting position. All exterior background, architecture, light, and spatial relation for outside shots must come from <Picture 4> only.
<Subject 6> is the inner courtyard environment taken only from <Picture 5>: the thatched-hall steps, stone paving, plum tree, and Liu Bei's waiting position at the foot of the steps. All interior background, architecture, light, and spatial relation for the courtyard wait must come from <Picture 5> only.
<Picture 4> is the sole exterior scene and composition reference for [Shot 1] and [Shot 3], defining the outer gate, fence, outside waiting space, and the spatial relation that Guan Yu and Zhang Fei remain outside the yard.
<Picture 5> is the sole interior scene and composition reference for [Shot 2], defining the thatched-hall steps, courtyard paving, plum tree, and where Liu Bei stands waiting alone at the foot of the steps.
<Picture 1>, <Picture 2>, and <Picture 3> are identity-only character references and must never be used as background or location sources.

summary:
[reference generation] Continuing after the page boy has opened the gate, <Subject 1> quietly tells <Subject 4> not to disturb the master and signals <Subject 2> and <Subject 3> to stay outside in the exterior space of <Subject 5> from <Picture 4>; then <Subject 1> alone enters the inner courtyard of <Subject 6> from <Picture 5>, stands still at the foot of the thatched-hall steps as plum petals fall on his shoulder, while outside <Subject 2> and <Subject 3> simply stand and wait beyond the gate without entering.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - face, beard, hair, robe, and body type from <Picture 1> are retained; he alone enters the yard and waits at the foot of the steps.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - face, long beard, hair, clothing, and body type from <Picture 2> are retained; he remains outside the gate/fence at all times, standing still, and never enters the courtyard.
<Subject 3> (appears in [Shot 1], [Shot 3]): fully_preserved - face, beard, hair, clothing, and body type from <Picture 3> are retained; he remains outside the gate/fence at all times, standing still and obediently waiting, and never enters the courtyard.
<Subject 4> (appears in [Shot 1] only): partially_preserved - present only for the quiet exchange at the opened gate, then drops out of later shots.
<Subject 5> (appears in [Shot 1], [Shot 3]): fully_preserved - outer gate, fence, exterior space, and outside waiting position from <Picture 4> are retained without relocating architecture.
<Subject 6> (appears in [Shot 2] only): fully_preserved - thatched-hall steps, stone paving, plum tree, light, and waiting position from <Picture 5> are retained; no new interior path is invented.
<Picture 4> (exterior composition for [Shot 1], [Shot 3]): fully_preserved - sole exterior background source.
<Picture 5> (interior composition for [Shot 2]): fully_preserved - sole interior background source.
<Picture 1>, <Picture 2>, <Picture 3> (identity only): fully_preserved - used only for character appearance, never as background.

detailed_description:
The target video is live-action cinematic Three Kingdoms drama, continuing directly after the previous beat in which the page boy has already opened the outer courtyard gate. Character appearances come only from their identity references; all backgrounds come only from the two scene references.
[Shot 1] At the opened outer courtyard gate in the exterior space of <Subject 5> from <Picture 4>, <Subject 1> stands just outside the gateway with a respectful, restrained expression after the prior exchange. <Subject 4> remains at the gate. Softly, lightly, and with deference, <Subject 1> (S1) says, <d>[Chinese] 切勿惊扰先生。我等在此等候。</d> He then turns and signals <Subject 2> and <Subject 3> to stay outside and not enter the yard. <Subject 2> and <Subject 3> halt outside the outer gate / beyond the fence in the waiting position defined by <Picture 4>; they do not step into the courtyard. After the signal, <Subject 1> alone walks lightly through the open gate into the yard. Camera stays with the exterior spatial relation of <Picture 4>: outside waiting space → outer gate → courtyard beyond. Guan Yu and Zhang Fei remain outside.
[Shot 2] At 00:05.500, cut into the interior courtyard of <Subject 6> from <Picture 5>. <Subject 1> is already inside and walks slowly to the foot of the thatched-hall steps. He stops directly below the steps—not at the outer gate, not midway on a new invented path—body upright, hands hanging naturally or resting quietly before him, waiting in silence. Afternoon light leans slightly westward; the yard is quiet; the plum tree stirs gently. A light breeze passes and a few plum petals drift down onto his shoulder. He does not move, does not brush the petals away, does not look around, and does not speak. Extreme patience and respect. Critical: only <Subject 1> is inside; <Subject 2> and <Subject 3> must not appear in the interior background.
[Shot 3] At 00:10.000, cut back outside the outer gate / beyond the fence in the exterior space of <Subject 5> from <Picture 4>, preserving that outside waiting layout. <Subject 2> and <Subject 3> simply stand still outside and wait obediently—no pacing, no stamping, no ear-rubbing, no restless twisting, no shouting, and no attempt to rush into the yard. Both men remain beyond the gate/fence and never enter the courtyard. No dialogue.

overall_soundscape:
Quiet early-afternoon courtyard air after the gate is open; Liu Bei's low respectful voice in Shot 1; soft footfalls as he alone enters; faint breeze and a near-silent petal fall in Shot 2; outside in Shot 3, only soft outdoor stillness around Guan Yu and Zhang Fei standing still.

non_diegetic_music:
Sparse restrained guqin under the quiet instruction, almost still during Liu Bei's silent wait under falling petals, then a soft unresolved hold over the brothers standing quietly outside.
```

