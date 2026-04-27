# USER

## ç»´æŠ¤è§„åˆ™

- æ¯å®Œæˆä¸€ä¸ªå¯ç‹¬ç«‹éªŒæ”¶çš„æ¨¡å—ã€é˜¶æ®µæˆ–é‡è¦ä¿®å¤åŽï¼Œç«‹å³è¿½åŠ ä¸€æ¡è®°å½•åˆ°æœ¬æ–‡ä»¶ã€?
- æ¯æ¡è®°å½•è‡³å°‘åŒ…å«ï¼šæ—¥æœŸã€æ¨¡å—åã€å®Œæˆå†…å®¹ã€å½±å“èŒƒå›´ã€éªŒè¯ç»“æžœã€?
- æäº¤ Git å‰ï¼Œå…ˆæ£€æŸ¥æœ¬æ–‡ä»¶æ˜¯å¦å·²åŒæ­¥æ›´æ–°ï¼›å¦‚æžœæ²¡æœ‰ï¼Œéœ€è¦å…ˆè¡¥é½è®°å½•å†æäº¤ã€?
- è¿è¡Œæ—¶äº§ç‰©ã€ä¸´æ—¶è°ƒè¯•ç»“è®ºä¸è¦å†™æˆæ­£å¼æ¨¡å—è®°å½•ï¼›åªè®°å½•å¯å¤çŽ°ã€å¯äº¤ä»˜çš„å¼€å‘ç»“æžœã€?

## å¼€å‘è®°å½?

### 2026-04-26 | PostgreSQL durable state ä¸?checkpoint æŒä¹…åŒ?

- å®Œæˆå†…å®¹ï¼?
  - æ–°å¢ž `app/storage/postgres.py`ï¼Œå°è£?PostgreSQL è¿è¡Œæ—¶çŠ¶æ€å­˜å–ã€?
  - æ–°å¢ž `app/core/runtime.py`ï¼Œç»Ÿä¸€ç®¡ç† LangGraph checkpoint backend ä¸Žçº¿ç¨‹æ€åŠ è½½ã€?
  - æ‰©å±• `app/memory/checkpoint.py`ã€`app/config/settings.py`ã€`pyproject.toml`ï¼Œæ”¯æŒ?PostgreSQL æŒä¹…åŒ–é…ç½®ä¸Žä¾èµ–ã€?
  - æ‰“é€?graph state åŠ è½½ã€æŒä¹…åŒ– checkpoint ä¸Žåº”ç”¨çº§ runtime state é•œåƒå†™å…¥é€»è¾‘ã€?
- å½±å“èŒƒå›´ï¼?
  - `app/core/agent.py`
  - `app/core/graph.py`
  - `app/memory/checkpoint.py`
  - `app/storage/postgres.py`
  - `app/core/runtime.py`
- éªŒè¯ç»“æžœï¼?
  - `tests/test_checkpoint_store.py`
  - `tests/test_graph_runtime.py`

### 2026-04-26 | å›¾åƒæ£€æµ‹è·¯ç”±ä¸Žä¸“ä¸šæ¨¡åž‹æŽ¥å…¥

- å®Œæˆå†…å®¹ï¼?
  - æ‰©å±• `app/tools/image_anomaly_detection.py`ï¼Œæ”¯æŒé€šç”¨è§†è§‰æ¨¡åž‹ä¸Žä¸“ä¸šå¼‚å¸¸æ£€æµ‹åŽç«¯è·¯ç”±ã€?
  - å¢žåŠ ä¸“ä¸šæ¨¡åž‹æœåŠ¡é…ç½®é¡¹ï¼Œå…è®¸é€šè¿‡é¡¹ç›®é…ç½®åˆ‡æ¢ `qwen` ä¸?`anomalygpt`ã€?
  - è¡¥å……å¼‚å¸¸åŒºåŸŸå®šä½ç»“æžœç»“æž„ï¼Œç»Ÿä¸€è¾“å‡ºå¼‚å¸¸åˆ—è¡¨ä¸Žå®šä½ä¿¡æ¯ã€?
- å½±å“èŒƒå›´ï¼?
  - `app/tools/image_anomaly_detection.py`
  - `app/core/tools.py`
  - `app/api/main.py`
  - `app/config/settings.py`
- éªŒè¯ç»“æžœï¼?
  - `tests/test_image_anomaly_detection_router.py`

### 2026-04-26 | æœ¬åœ° AnomalyGPT æœåŠ¡ä¸?Docker ä¾§è½¦

- å®Œæˆå†…å®¹ï¼?
  - æ–°å¢ž `services/anomalygpt_local/` æœ¬åœ°æœåŠ¡éª¨æž¶ã€?
  - æä¾› `Dockerfile`ã€`docker-compose.yml`ã€`start_service.ps1` ä¸ŽæœåŠ¡è¯´æ˜Žæ–‡æ¡£ã€?
  - æ”¯æŒé¡¹ç›®ä¾§é€šè¿‡ HTTP è°ƒç”¨æœ¬åœ°éƒ¨ç½²çš„ä¸“ä¸šå¼‚å¸¸æ£€æµ‹æœåŠ¡ã€?
- å½±å“èŒƒå›´ï¼?
  - `services/anomalygpt_local/app.py`
  - `services/anomalygpt_local/Dockerfile`
  - `services/anomalygpt_local/docker-compose.yml`
  - `services/anomalygpt_local/README.md`
- éªŒè¯ç»“æžœï¼?
  - æœåŠ¡æŽ¥çº¿ç”±ä¸»é“¾è·¯æµ‹è¯•è¦†ç›–ï¼Œé…ç½®è¯´æ˜Žå·²å†™å…¥é¡¹ç›®æ–‡æ¡£ã€?

### 2026-04-26 | å‰ç«¯æ”¶æ•›ä¸ºæ ¸å¿ƒæµç¨‹é¡µ

- å®Œæˆå†…å®¹ï¼?
  - å°†å‰ç«¯æ”¶æ•›ä¸ºå•é¡µæ ¸å¿ƒæµç¨‹ï¼Œå‡å°‘åˆ†æ•£é¡µé¢ä¸Žé‡å¤äº¤äº’ã€?
  - `web/index.html` è°ƒæ•´ä¸ºå›´ç»•æ£€æµ‹ã€è¿½é—®ã€æŠ¥å‘Šç”Ÿæˆçš„ä¸»å·¥ä½œæµã€?
  - ä¿æŒåŽç«¯ API ä¸å˜ï¼Œå‰ç«¯ä»…åšäº¤äº’ä¸Žå±•ç¤ºå±‚ç®€åŒ–ã€?
- å½±å“èŒƒå›´ï¼?
  - `web/index.html`
  - `README.md`
- éªŒè¯ç»“æžœï¼?
  - `tests/test_main_flow_smoke.py`

### 2026-04-26 | å¤?Agent Phase 1ï¼šæœ‰ä¸»æŽ§çš„ç›‘ç£å¼æž¶æž„éª¨æž¶

- å®Œæˆå†…å®¹ï¼?
  - æ–°å¢ž supervisorã€visionã€knowledgeã€report å››ç±» agent éª¨æž¶ã€?
  - æ–°å¢ž `AgentEnvelope` ä½œä¸ºä¸»æŽ§ä¸Žä¸“å®?agent çš„ç»Ÿä¸€é€šä¿¡å¥‘çº¦ã€?
  - æ‰©å±• `DetectionState`ï¼Œå¢žåŠ?`agent_outputs`ã€`agent_trace`ã€`active_agent`ã€`shared_context`ã€?
  - é‡å†™é¡¶å±‚ graphï¼Œå°†æ‰§è¡Œæµå‡çº§ä¸º supervisor è§„åˆ’ã€æ‰§è¡Œã€åˆå¹¶çš„å—æŽ§æµç¨‹ã€?
  - ä¿æŒçŽ°æœ‰å¤–éƒ¨ API ä¸Žå‰ç«¯åè®®ä¸å˜ï¼Œå…ˆå®Œæˆå†…éƒ¨ç¼–æŽ’è¿ç§»ã€?
- å½±å“èŒƒå›´ï¼?
  - `app/agents/`
  - `app/orchestration/envelope.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `app/memory/state.py`
- éªŒè¯ç»“æžœï¼?
  - `tests/test_phase1_multi_agent.py`

### 2026-04-26 | ä¸»é“¾è·¯å›žå½’éªŒè¯?

- å®Œæˆå†…å®¹ï¼?
  - å¯?durable stateã€å›¾åƒè·¯ç”±ã€å¤š Agent Phase 1 ä¸Žä¸»æµç¨‹è¿›è¡Œå›žå½’éªŒè¯ã€?
- éªŒè¯ç»“æžœï¼?
  - æ‰§è¡Œï¼?
    - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py`
  - ç»“æžœï¼?
    - `19 passed in 10.44s`

### 2026-04-26 | å·¥ä½œè®°å¿†æ–‡ä»¶æ²»ç†ï¼ˆæ–¹æ¡?Bï¼?

- å®Œæˆå†…å®¹ï¼?
  - å°?`app/data/memory/working_memory.json` å®šä¹‰ä¸ºè¿è¡Œæ—¶æ–‡ä»¶ï¼Œä¸å†çº³å…?Git è·Ÿè¸ªã€?
  - æ–°å¢ž `app/data/memory/working_memory.example.json` ä½œä¸ºå¯æäº¤çš„ç»“æž„æ ·ä¾‹ã€?
  - åœ?`.gitignore` ä¸?`README.md` ä¸­è¡¥å……è¿è¡Œæ—¶æ–‡ä»¶ä¸Žæ ·ä¾‹æ–‡ä»¶çš„ä½¿ç”¨è¯´æ˜Žã€?
- å½±å“èŒƒå›´ï¼?
  - `.gitignore`
  - `README.md`
  - `app/data/memory/working_memory.example.json`
- éªŒè¯ç»“æžœï¼?
  - è¿è¡Œæ—¶é€»è¾‘ä»ç„¶è¯»å–/å†™å…¥ `working_memory.json`ï¼Œä»“åº“ä¸­æ”¹ä¸ºä¿ç•™æ ·ä¾‹æ–‡ä»¶ä¾›å‚è€ƒã€?

### 2026-04-26 | å¤?Agent Phase 2ï¼šä¸»æŽ§å¢žå¼ºä¸Žä¸‹æ¸¸çŠ¶æ€åˆ‡æ?

- å®Œæˆå†…å®¹ï¼?
  - å°?`SupervisorAgent` ä»Žçº¯è§„åˆ™è·¯ç”±å‡çº§ä¸ºâ€œLLM ç»“æž„åŒ–è§„åˆ?+ è§„åˆ™å›žé€€â€çš„ä¸»æŽ§æ¨¡å¼ã€?
  - `supervisor_merge_node` çŽ°åœ¨ä¼šæŠŠ vision/knowledge/report çš„ç»“æžœåŒæ­¥å›ž `result` ä¸?`shared_context`ï¼Œå‡å°‘å¯¹æ—?`tool_outputs` çš„ä¾èµ–ã€?
  - `answer_node` æ”¹ä¸ºä¼˜å…ˆæ¶ˆè´¹ `shared_context["vision"]` ä¸?`shared_context["knowledge"]`ï¼Œç¡®ä¿å›žç­”çœŸæ­£å»ºç«‹åœ¨ä¸“å®¶ Agent è¾“å‡ºä¸Šã€?
  - æŠ¥å‘Šç”Ÿæˆé€»è¾‘ä»?`app.core` è§£è€¦åˆ° `app/agents/report/service.py`ï¼Œ`ReportAgent` ä¸?graph/report å…¥å£ç»Ÿä¸€å¤ç”¨æ–°æœåŠ¡ã€?
  - `self_reflect_node` æ”¹ä¸ºä¼˜å…ˆåŸºäºŽå…±äº«è§†è§‰ç»“æžœè¿›è¡Œåˆ¤æ–­ï¼Œä¸Žæ–°çš„å¤?Agent çŠ¶æ€æµä¿æŒä¸€è‡´ã€?
- å½±å“èŒƒå›´ï¼?
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/answer_node.py`
  - `app/core/self_reflect.py`
  - `app/agents/report/service.py`
  - `app/agents/report/agent.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `tests/test_phase1_multi_agent.py`
- éªŒè¯ç»“æžœï¼?
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - ç»“æžœï¼š`22 passed`

### 2026-04-26 | å¤?Agent Phase 3ï¼šæ¾„æ¸?Agentã€å…±äº«ä¸Šä¸‹æ–‡ Schemaã€å¯ä¸­æ–­æŒ‚èµ·é“¾è·¯

- å®Œæˆå†…å®¹ï¼?
  - æ–°å¢ž `ClarificationAgent`ï¼Œå½“ `self_reflect` åˆ¤æ–­éœ€è¦äººå·¥è¡¥å……æ—¶ï¼Œç”±ä¸»æŽ§å…ˆç”Ÿæˆç»“æž„åŒ–æ¾„æ¸…è¯·æ±‚ï¼Œå†è¿›å…¥ç­‰å¾…ç”¨æˆ·èŠ‚ç‚¹ã€?
  - æ–°å¢ž `app/orchestration/context.py`ï¼Œå°† `shared_context` ç»“æž„åŒ–ä¸º `vision/knowledge/report/clarification` å››ç±»ä¸Šä¸‹æ–‡æ¨¡åž‹ã€?
  - é‡å†™ graph è·¯ç”±ï¼Œä½¿ `wait_user` æˆä¸ºçœŸæ­£å¯ä¸­æ–­èŠ‚ç‚¹ï¼šé¦–æ¬¡æŒ‚èµ·ç›´æŽ¥ç»“æŸï¼Œç”¨æˆ·å›žå¤åŽå†å›žåˆ?supervisor ç»§ç»­ç¼–æŽ’ã€?
  - `get_pending_task`ã€`run_detection`ã€`run_chat`ã€`continue_detection`ã€`generate_report` ç»Ÿä¸€æš´éœ² `agent_trace`ï¼Œä¾¿äºŽå‰ç«¯å±•ç¤ºå’ŒæŽ’éšœã€?
  - ä¿®æ­£ `build_continue_state` é€»è¾‘ï¼Œé¿å…ç»§ç»­æ‰§è¡Œæ—¶é‡å¤æŠŠç”¨æˆ·å›žå¤ç›´æŽ¥å†™å…¥åŽ†å²ï¼Œæ”¹ä¸ºäº¤ç”± `wait_user_node` æ¶ˆè´¹ã€?
- å½±å“èŒƒå›´ï¼?
  - `app/orchestration/context.py`
  - `app/memory/state.py`
  - `app/agents/clarification/`
  - `app/agents/factory.py`
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/wait_user.py`
  - `app/core/agent.py`
  - `app/core/answer_node.py`
  - `app/core/self_reflect.py`
  - `app/agents/report/service.py`
  - `tests/test_phase1_multi_agent.py`
- éªŒè¯ç»“æžœï¼?
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - ç»“æžœï¼š`24 passed`
### 2026-04-27 | Multi-Agent Phase 4A/4B | structured execution plan + actionable retry
- å®Œæˆå†…å®¹ï¼?
  - å°?supervisor è§„åˆ’ç»“æžœä»Žæ‰å¹?`planned_agents` å‡çº§ä¸ºç»“æž„åŒ– `execution_plan.steps`ï¼Œæ¯ä¸?step è®°å½• `id / agent / goal / depends_on / retryable`ã€?
  - æ‰©å±• `DetectionState`ï¼Œæ–°å¢?`execution_plan`ã€`step_status`ã€`step_attempts`ã€`step_outputs`ã€`last_failed_step` ä»¥åŠ `retry_target / retry_reason / retry_strategy`ã€?
  - æ”¹é€?`supervisor_plan_node` ä¸?`supervisor_execute_node`ï¼ŒæŒ‰ç»“æž„åŒ?step æ‰§è¡Œå¹¶æŠŠ step çº§çŠ¶æ€å†™å›?runtime metadataã€?
  - æ”¹é€?`self_reflect_node`ï¼Œå½“åˆ¤å®šéœ€è¦?retry æ—¶è¾“å‡ºæ˜Žç¡®çš„ retry ç›®æ ‡å’Œç­–ç•¥ï¼Œä¸å†åªè¿”å›žæŠ½è±¡çš„ `retry` å†³ç­–ã€?
  - è°ƒæ•´ä¸»è¿è¡Œæ—¶è¿”å›žä¸?SSE èŠ‚ç‚¹è§‚æµ‹ï¼Œè¡¥å…?`execution_plan / step_status / step_attempts`ï¼Œå¹¶åˆ‡æ¢åˆ°çœŸå®?supervisor èŠ‚ç‚¹åã€?
  - åœ¨æ‰§è¡Œå±‚æ–°å¢žæŒ‰ä¾èµ–åˆ†æ‰¹æ‰§è¡Œèƒ½åŠ›ï¼šåŒä¸€æ‰¹æ— ä¾èµ– step æ”¯æŒå¹¶å‘ï¼Œè·¨æ‰¹æ¬¡ä¿æŒé¡ºåºï¼Œä½œä¸ºåŽç»­æ›´å®Œæ•´ DAG ç¼–æŽ’çš„åŸºç¡€ã€?
  - å°?`supervisor_merge_node` é‡æž„ä¸?agent-specific merge adaptersï¼Œé™ä½Žå¯¹ `vision / knowledge / clarification / report` çš„ç¡¬ç¼–ç è€¦åˆï¼Œä¸ºåŽç»­æ–°å¢ž specialist agent é¢„ç•™ç¨³å®šæ‰©å±•ç‚¹ã€?
  - æ–°å¢ž `execution_events` æ—¶é—´çº¿ï¼Œè®°å½• `plan_created / step_started / step_completed / step_failed / task_suspended / task_resumed` ç­‰äº‹ä»¶ï¼Œå¹¶åŒæ­¥æš´éœ²åˆ° API metadataã€pending æŸ¥è¯¢ç»“æžœä¸?SSE `execution_event` / `final_result.metadata`ã€?
  - å‰ç«¯ä¸»å·¥ä½œå°æ–°å¢ž multi-agent timeline é¢æ¿ï¼ŒåŸºäº?`execution_plan / execution_events / step_status / step_attempts` æ¸²æŸ“ step æ¦‚è§ˆä¸Žäº‹ä»¶æµï¼Œå¸®åŠ©ç”¨æˆ·ç›´æŽ¥è§‚å¯?supervisor ç¼–æŽ’è¿‡ç¨‹ã€?
  - æµå¼æŽ¥å£ `final_result` è¡¥å…… answer / anomalies / pending ä¿¡æ¯ï¼Œå‰ç«¯é¦–è½®æ£€æµ‹ä¸Žè¿½é—®åˆ‡æ¢åˆ?`/v1/stream`ï¼Œæ‰§è¡Œè¿‡ç¨‹ä¸­å¯å®žæ—¶æ»šåŠ¨å±•ç¤?execution events ä¸Žå¢žé‡å›žç­”ã€?
  - `/v1/stream` æ–°å¢ž continue åˆ†æ”¯ï¼šè¡¨å•æºå¸?`user_reply` æ—¶èµ°æµå¼ç»§ç»­æ¾„æ¸…é“¾è·¯ï¼Œå‰ç«?`continueTask()` åŒæ­¥åˆ‡æ¢ä¸ºå®žæ—¶æ‰§è¡Œæ¨¡å¼ï¼Œä¸‰æ¡ä¸»è·¯å¾„ï¼ˆdetect / chat / continueï¼‰çŽ°å·²ç»Ÿä¸€åˆ°åŒä¸€å¥?timeline æ›´æ–°æœºåˆ¶ã€?
- å½±å“èŒƒå›´ï¼?
  - `app/agents/supervisor/agent.py`
  - `app/agents/supervisor/__init__.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/self_reflect.py`
  - `app/core/agent.py`
  - `app/core/wait_user.py`
  - `app/memory/state.py`
  - `tests/test_phase1_multi_agent.py`
  - `tests/test_main_flow_smoke.py`
  - `web/index.html`
- éªŒè¯ç»“æžœï¼?
  - `pytest tests/test_phase1_multi_agent.py -q`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py -q`
  - `node` è§£æž `web/index.html` å†…è”è„šæœ¬è¯­æ³•æ£€æŸ?
  - `pytest tests/test_main_flow_smoke.py -q`
  - ç»“æžœï¼š`22 passed`ï¼Œå‰ç«¯ä¸»æµç¨‹ä¸Žæµå¼?continue åˆ†æ”¯é€šè¿‡

### 2026-04-27 | Frontend Timeline UX | filters, collapse, detail inspector
- Íê³ÉÄÚÈÝ£º
  - Îª multi-agent timeline Ãæ°åÐÂÔö×´Ì¬É¸Ñ¡£º`È«²¿ / ÔËÐÐÖÐ / Ê§°Ü / µÈ´ý / Íê³É`£¬³¤ÈÎÎñÅÅÕÏÊ±¿ÉÒÔ¿ìËÙ¾Û½¹Òì³£ºÍ¹ÒÆð½Úµã¡£
  - ÐÂÔö `Steps / Events` ÕÛµþ¿ª¹Ø£¬ÊÂ¼þÁ÷¹ý³¤Ê±¿ÉÒÔÏÈÊÕÆðÒ»²à£¬±£Áôµ±Ç°¿´°åµÄÉ¨ÃèÐ§ÂÊ¡£
  - ÐÂÔöÏêÇéÃæ°å£¬µã»÷ step »òÊÂ¼þºó¿É²é¿´ `agent / step_id / attempt / depends_on` µÈ¹Ø¼ü×Ö¶ÎºÍÔ­Ê¼ JSON£¬·½±ã¾«È·ÅÅÕÏ¡£
  - timeline ÄÚ²¿¸ÄÎª¡°¸ÅÀÀ + ÊÂ¼þÁ÷ + ÏêÇé¼ìÊÓÆ÷¡±ÈýÀ¸½á¹¹£¬Í¬Ê±¼æÈÝÒÆ¶¯¶Ëµ¥ÁÐÕ¹Ê¾¡£
- Ó°Ïì·¶Î§£º
  - `web/index.html`
- ÑéÖ¤½á¹û£º
  - `node` ½âÎö `web/index.html` ÄÚÁª½Å±¾Óï·¨¼ì²é
  - `pytest tests/test_main_flow_smoke.py tests/test_phase1_multi_agent.py tests/test_graph_runtime.py -q`
  - ½á¹û£º`22 passed`

### 2026-04-27 | Architecture Convergence Phase 1 | services split and orchestration cleanup
- Íê³ÉÄÚÈÝ£º
  - ½«ÈÎÎñÔËÐÐÈë¿Ú´Ó `app/core/agent.py` ²ð·Öµ½ `app/services/`£º·Ö±ðÂäµ½ `task_runner.py`¡¢`streaming.py`¡¢`state_rehydration.py`£¬½µµÍÔËÐÐÈë¿Ú¡¢SSE¡¢×´Ì¬»Ö¸´Ö®¼äµÄñîºÏ¡£
  - ½« supervisor ÔËÐÐÊ±´Ó `app/core/supervisor.py` ²ð·Öµ½ `app/orchestration/`£ºÐÂÔö `planner_runtime.py`¡¢`step_executor.py`¡¢`merge_adapters.py`¡¢`events.py`¡£
  - ±£Áô `app/core/agent.py` Óë `app/core/supervisor.py` ×÷Îª¼æÈÝÃÅÃæ£¬±ÜÃâÏÖÓÐ graph Óë²âÊÔµ¼ÈëÂ·¾¶Á¢¼´Ê§Ð§¡£
  - Îª `planner / executor / consolidate / supplement` ²¹³ä legacy ±ê¼Ç£¬Ã÷È·ËüÃÇ²»ÊÇµ±Ç° supervisor Ö÷Á´Â·µÄÒ»²¿·Ö¡£
  - ÐÂÔö `Docs/architecture.md`£¬ËµÃ÷ÏÖÒÛ·Ö²ã¡¢Ö÷Á÷³Ì¡¢ÔËÐÐÈë¿Ú¡¢shared context Óë legacy Ä£¿é±ß½ç¡£
- Ó°Ïì·¶Î§£º
  - `app/services/`
  - `app/orchestration/`
  - `app/core/agent.py`
  - `app/core/supervisor.py`
  - `app/api/main.py`
  - `app/core/planner.py`
  - `app/core/executor.py`
  - `app/core/consolidate.py`
  - `app/core/supplement.py`
  - `tests/test_main_flow_smoke.py`
  - `tests/test_phase1_multi_agent.py`
  - `Docs/architecture.md`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_agent.py tests/test_main_flow_smoke.py tests/test_phase1_multi_agent.py tests/test_graph_runtime.py -q`
  - `node` ½âÎö `web/index.html` ÄÚÁª½Å±¾Óï·¨¼ì²é
  - ½á¹û£º`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2A | shared context access helpers
- Íê³ÉÄÚÈÝ£º
  - ÐÂÔö `app/orchestration/context_store.py`£¬Í³Ò»¹ÜÀí `pending_clarification / pending_question / rag_context` ÕâÀàºËÐÄÒµÎñÉÏÏÂÎÄµÄ¶ÁÐ´Óë¼æÈÝ shadow Í¬²½¡£
  - `merge_adapters`¡¢`wait_user`¡¢`state_rehydration`¡¢`answer_node` ¸ÄÎªÍ¨¹ý helper ·ÃÎÊ¹²ÏíÉÏÏÂÎÄ£¬¼õÉÙ `state.context[...]` µÄ·ÖÉ¢ÊÖÐ´¡£
  - ±£Áô `context` ¼æÈÝ×Ö¶ÎÊä³ö£¬µ«½« `shared_context` ×÷ÎªÓÅÏÈ¶ÁÈ¡À´Ô´£¬ÎªºóÐø¼ÌÐøÊÕÁ² `context` ×ö×¼±¸¡£
- Ó°Ïì·¶Î§£º
  - `app/orchestration/context_store.py`
  - `app/orchestration/merge_adapters.py`
  - `app/core/wait_user.py`
  - `app/core/answer_node.py`
  - `app/services/state_rehydration.py`
  - `tests/test_phase1_multi_agent.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - `node` ½âÎö `web/index.html` ÄÚÁª½Å±¾Óï·¨¼ì²é
  - ½á¹û£º`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2B | state runtime grouping views
- Íê³ÉÄÚÈÝ£º
  - ÔÚ `app/memory/state.py` ÖÐÐÂÔö `TaskRuntimeState`¡¢`OrchestrationRuntimeState`¡¢`DomainRuntimeState`£¬Îª `DetectionState` Ìá¹©ÕýÊ½µÄ·Ö×éÊÓÍ¼¡£
  - ÐÂÔö `task_runtime()`¡¢`orchestration_runtime()`¡¢`domain_runtime()`£¬½«ÈÎÎñÊäÈë/»á»°¡¢±àÅÅÔËÐÐÌ¬¡¢ÁìÓò½á¹ûÉÏÏÂÎÄ°´Ö°Ôð·Ö×éÊä³ö¡£
  - ±£³ÖÏÖÓÐ checkpoint ¶¥²ã½á¹¹²»±ä£¬ÏÈÓÃÊÓÍ¼·½Ê½ÎªºóÐø¸ü³¹µ×µÄ×´Ì¬²ð·ÖÆÌÂ·£¬½µµÍÒ»´ÎÐÔÖØ¹¹·çÏÕ¡£
  - ÔÚ `Docs/architecture.md` ÖÐ²¹³ä state grouping ËµÃ÷£¬Ã÷È·ÕâÊÇÎ´À´×´Ì¬Ä£ÐÍÊÕÁ²µÄÇ¨ÒÆÂ·¾¶¡£
- Ó°Ïì·¶Î§£º
  - `app/memory/state.py`
  - `tests/test_phase1_multi_agent.py`
  - `Docs/architecture.md`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2C | runtime views consumed in core paths
- Íê³ÉÄÚÈÝ£º
  - ½« graph Â·ÓÉÅÐ¶Ï¸ÄÎªÓÅÏÈ¶ÁÈ¡ `task_runtime()`¡¢`orchestration_runtime()`¡¢`domain_runtime()`£¬ÈÃ `execution_plan / reflection_decision / report_requested / clarification` ÕâÀà·Ö²ã±ß½çÔÚºËÐÄÁ÷³ÌÖÐÕæÕý±»Ïû·Ñ¡£
  - `self_reflect_node` ¸ÄÎªÍ¨¹ý runtime view ¶ÁÈ¡ `loop_count` Óë task parameters£¬¼õÉÙ¶Ô `DetectionState` ¶¥²ã×Ö¶ÎµÄÖ±½ÓñîºÏ¡£
  - `answer_node` ¸ÄÎªÍ¨¹ý `task_runtime()` ¶ÁÈ¡ÈÎÎñÓë»á»°ÀúÊ·£¬¿ªÊ¼°Ñ×îÖÕ»Ø´ð½Úµã¶Ô¶¥²ã state Æ½ÃæµÄÒÀÀµÊÕÕ­¡£
  - `planner_runtime` µÄÖ´ÐÐÈë¿Ú¸ÄÎªÍ¨¹ý `orchestration_runtime()` ¶ÁÈ¡¼Æ»®Óë step Íê³ÉÌ¬£¬¸øºóÐø¸ü³¹µ×µÄ×´Ì¬²ð·Ö¼ÌÐøÆÌÂ·¡£
- Ó°Ïì·¶Î§£º
  - `app/core/graph.py`
  - `app/core/self_reflect.py`
  - `app/core/answer_node.py`
  - `app/orchestration/planner_runtime.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2D | runtime apply helpers for write paths
- Íê³ÉÄÚÈÝ£º
  - ÔÚ `DetectionState` ÖÐÐÂÔö `apply_task_runtime()`¡¢`apply_orchestration_runtime()`¡¢`apply_domain_runtime()`£¬Îª grouped runtime Ìá¹©ÕýÊ½Ð´»ØÈë¿Ú¡£
  - `prepare_followup_state()` ¸ÄÎªÍ¨¹ý runtime apply helpers ÖØÖÃ follow-up ÂÖ´ÎËùÐè×Ö¶Î£¬¼õÉÙ¶Ô¶¥²ã state ×Ö¶ÎµÄÉ¢Ð´¡£
  - `wait_user_node()` ¸ÄÎªÍ¨¹ý `task_runtime` / `orchestration_runtime` ¸üÐÂ»á»°¡¢¹ÒÆð»Ö¸´ÊÂ¼þÓë `needs_user_input` ×´Ì¬£¬ÈÃ grouped runtime ¿ªÊ¼³Ðµ£Ð´Â·¾¶Ö°Ôð¡£
  - ÐÂÔö²âÊÔ¸²¸Ç runtime apply helpers£¬È·ÈÏ·Ö×éÊÓÍ¼²»½ö¿É¶Á£¬Ò²ÄÜÎÈ¶¨Ð´»ØÖ÷ state¡£
- Ó°Ïì·¶Î§£º
  - `app/memory/state.py`
  - `app/services/state_rehydration.py`
  - `app/core/wait_user.py`
  - `tests/test_phase1_multi_agent.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2E | orchestration writes via grouped runtime
- Íê³ÉÄÚÈÝ£º
  - `supervisor_plan_node()` Óë `supervisor_execute_node()` ¿ªÊ¼Í¨¹ý `apply_orchestration_runtime()` / `apply_domain_runtime()` »ØÐ´Ö´ÐÐ¼Æ»®¡¢step ×´Ì¬¡¢attempt¡¢step outputs Óë agent outputs¡£
  - `supervisor_merge_node()` Ïà¹Ø adapters ¿ªÊ¼Í¨¹ý grouped runtime Ð´»Ø `tool_outputs`¡¢`shared_context`¡¢`unknown_anomaly_types` Óë `needs_user_input`£¬¼õÉÙ orchestration ²ã¶Ô `DetectionState` ¶¥²ã×Ö¶ÎµÄÉ¢Ð´¡£
  - ²¹Æë `execution_events` ÔÚ¶¥²ã state Óë orchestration runtime ÊÓÍ¼Ö®¼äµÄÍ¬²½£¬±ÜÃâÊÂ¼þ append ºó±»¾ÉÊÓÍ¼¸²¸Ç¡£
- Ó°Ïì·¶Î§£º
  - `app/orchestration/planner_runtime.py`
  - `app/orchestration/merge_adapters.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2F | result-side writes via grouped runtime
- Íê³ÉÄÚÈÝ£º
  - ÖØÐ´ `app/core/answer_node.py` Îª¸É¾»µÄ ASCII-safe ÊµÏÖ£¬²¢ÈÃ»Ø´ð½ÚµãÍ¨¹ý `task_runtime()` / `apply_task_runtime()` Óë `domain_runtime()` ¸üÐÂ»á»°²½Êý¡¢½á¹ûÉÏÏÂÎÄÓë»Ø´ðÂäÅÌ¡£
  - ÖØÐ´ `app/agents/report/service.py` Îª¸É¾»ÊµÏÖ£¬²¢ÈÃ±¨¸æÉú³ÉÂ·¾¶Í¨¹ý grouped runtime ¶ÁÈ¡ task/orchestration/domain ÐÅÏ¢£¬×îÖÕÍ¨¹ý `apply_domain_runtime()` »ØÐ´ report ½á¹ûÓë shared context¡£
  - ÇåÀí answer/report Á½¸ö½á¹û²àºËÐÄÎÄ¼þµÄÀúÊ·±àÂëÔëÉù£¬½µµÍºóÐø¼ÌÐøÖØ¹¹Ê±µÄÓï·¨ÓëÎÄ±¾Ëð»µ·çÏÕ¡£
- Ó°Ïì·¶Î§£º
  - `app/core/answer_node.py`
  - `app/agents/report/service.py`
- ÑéÖ¤½á¹û£º
  - `python -m py_compile app/core/answer_node.py app/agents/report/service.py`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2G | top-level compatibility clarified and supervisor reads tightened
- Íê³ÉÄÚÈÝ£º
  - Îª `DetectionState` ²¹³ä¶¥²ã×´Ì¬ËµÃ÷£¬Ã÷È· flat state ¼ÌÐø±£ÁôÓÃÓÚ checkpoint ¼æÈÝ£¬µ«ÐÂ´úÂëÓ¦ÓÅÏÈ×ß grouped runtime ÊÓÍ¼¡£
  - `SupervisorAgent` ¸ÄÎªÓÅÏÈÍ¨¹ý `task_runtime()`¡¢`orchestration_runtime()`¡¢`domain_runtime()` ¶ÁÈ¡ `report_requested`¡¢`needs_user_input`¡¢`retry_*`¡¢`agent_outputs`¡¢`shared_context` µÈ¹Ø¼ü×´Ì¬¡£
  - ÈÃ supervisor ¹æ»®²ã³ÉÎª¸üÃ÷È·µÄ¡°runtime view first¡± Ïû·ÑÕß£¬¼õÉÙ¶Ô `DetectionState` ¶¥²ã×Ö¶ÎµÄÖ±½Ó¶ÁÈ¡ñîºÏ¡£
- Ó°Ïì·¶Î§£º
  - `app/memory/state.py`
  - `app/agents/supervisor/agent.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2H | active path runtime-view-first completion
- Íê³ÉÄÚÈÝ£º
  - `self_reflect`¡¢`wait_user`¡¢`step_executor`¡¢`task_runner.generate_report` µÈÊ£ÓàÏÖÒÛÄ£¿é¼ÌÐøÊÕÁ²µ½ grouped runtime ¶ÁÐ´·½Ê½¡£
  - `planner_runtime` ÖÐ agent trace µÄÐ´»ØÒ²ÄÉÈë `apply_domain_runtime()` Â·¾¶£¬¼õÉÙ active path ÉÏ¶Ô¶¥²ã state µÄÉ¢Ð´²ÐÁô¡£
  - `Docs/architecture.md` ²¹³äÍê³ÉÌ¬ËµÃ÷£ºÏÖÒÛÖ÷Á´Â·ÒÑ¾­´ïµ½ runtime-view-first£¬¶¥²ã×Ö¶ÎÖ÷Òª³Ðµ£ checkpoint Óë¼æÈÝÖ°Ôð¡£
- Ó°Ïì·¶Î§£º
  - `app/core/self_reflect.py`
  - `app/core/wait_user.py`
  - `app/orchestration/step_executor.py`
  - `app/orchestration/planner_runtime.py`
  - `app/services/task_runner.py`
  - `Docs/architecture.md`
- ÑéÖ¤½á¹û£º
  - `python -m py_compile app/core/self_reflect.py app/core/wait_user.py app/orchestration/step_executor.py app/orchestration/planner_runtime.py app/services/task_runner.py`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | ä¸»æ–‡æ¡£æ”¶å£ä¸ŽæŽ¥å£è¯´æ˜Žç»Ÿä¸€

- å®Œæˆå†…å®¹ï¼?
  - å°?`README.md` é‡å†™ä¸ºå½“å‰é¡¹ç›®å”¯ä¸€ä¸»æ–‡æ¡£ï¼Œç»Ÿä¸€æè¿°çŽ°æœ‰ FastAPI è·¯ç”±ã€LangGraph å¤?Agent æµç¨‹ã€å‰ç«¯å…¥å£ã€RAGã€è§†è§‰åŽç«¯è·¯ç”±ã€checkpoint ä¸Žè®°å¿†ç­–ç•¥ã€?
  - ç§»é™¤ README ä¸­æ—§ç‰?JSON æ£€æµ‹ç¤ºä¾‹ã€æ—§é“¾å¼ `anomaly_detect/summarize` æµç¨‹ã€æ—§å¤šé¡µé¢å‰ç«¯æè¿°ç­‰è¿‡æ—¶å†…å®¹ã€?
  - åœ?README ä¸­æ˜Žç¡®åˆ—å‡ºå»ºè®®åˆ é™¤æˆ–å½’æ¡£çš„å†—ä½™æ–‡æ¡£ï¼Œä½œä¸ºåŽç»­æ–‡æ¡£æ¸…ç†ä¾æ®ã€?
- å½±å“èŒƒå›´ï¼?
  - `README.md`
  - `USER.md`
- éªŒè¯ç»“æžœï¼?
  - æœ¬æ¬¡ä¸ºæ–‡æ¡£æ•´ç†ï¼Œæœªæ”¹å˜è¿è¡Œæ—¶ä»£ç ã€?

### 2026-04-27 | è¿‡æ—¶æ–‡æ¡£æ¸…ç†

- å®Œæˆå†…å®¹ï¼?
  - åˆ é™¤å·²ç”±ä¸?README åˆå¹¶è¦†ç›–æˆ–ä¸Žå½“å‰æŽ¥å£ä¸åŒ¹é…çš„æ—§æ–‡æ¡£ã€?
  - ä¿ç•™ `Docs/01-LangChain.ipynb`ã€`Docs/02-LangGraph.ipynb`ã€`Docs/03-LangSmith.ipynb` ä½œä¸ºå­¦ä¹ ç¬”è®°ã€?
  - æ›´æ–° README æ–‡æ¡£ç»´æŠ¤ç­–ç•¥ï¼Œæ”¹ä¸ºè®°å½•å½“å‰å®žé™…ä¿ç•™æ–‡æ¡£ã€?
- å½±å“èŒƒå›´ï¼?
  - `README.md`
  - `USER.md`
  - `web/README.md`
  - `Docs/api_docs.md`
  - `Docs/function_docs.md`
  - `Docs/å¼€å‘æŒ‡å?md`
  - `Docs/2026-04-21-architecture_review.md`
  - `Docs/2026-04-21-implementation_update.md`
  - `Docs/agent_engineering_review.md`
- éªŒè¯ç»“æžœï¼?
  - å·²ç¡®è®¤ç›®æ ‡æ–‡æ¡£åˆ é™¤å®Œæˆï¼Œä¸‰ä¸ª notebook æœªåˆ é™¤ã€?

### 2026-04-27 | å‰ç«¯å…¥å£æ”¶æ•›ä¸ºå•é¡?

- å®Œæˆå†…å®¹ï¼?
  - å®¡æŸ¥ `web/` ä¸‹æ‰€æœ?HTML é¡µé¢ï¼Œç¡®è®¤é™¤ `index.html` å¤–å‡ä¸ºè·³è½¬åˆ°ä¸»é¡µé¢çš„å…¼å®¹å£³ã€?
  - æœç´¢é¡¹ç›®ä»£ç ã€æµ‹è¯•å’Œæ–‡æ¡£å¼•ç”¨ï¼Œç¡®è®¤æ—§ HTML é¡µé¢æœªè¢«è¿è¡Œæ—¶ä»£ç ä¾èµ–ã€?
  - åˆ é™¤ `chat.html`ã€`detection.html`ã€`expert_inspection.html`ã€`frontend_chat.html`ã€`rag.html`ï¼Œåªä¿ç•™ `web/index.html`ã€?
  - æ›´æ–° README ä¸­çš„å‰ç«¯ç›®å½•ç»“æž„å’Œè¯´æ˜Žã€?
- å½±å“èŒƒå›´ï¼?
  - `web/index.html`
  - `web/chat.html`
  - `web/detection.html`
  - `web/expert_inspection.html`
  - `web/frontend_chat.html`
  - `web/rag.html`
  - `README.md`
  - `USER.md`
- éªŒè¯ç»“æžœï¼?
  - `web/` ç›®å½•ä¸‹ä»…å‰?`index.html` ä¸€ä¸?HTML é¡µé¢ã€?

### 2026-04-27 | Memory Convergence | short-term writes, tool audit, and conversation compaction
- Íê³ÉÄÚÈÝ£º
  - nswer_node ÔÚÊ×´Î»Ø´ðºó²¹Æë ShortTermMemory Ð´Èë£¬²¢°Ñ 	ool_effect ÄÉÈë×îÖÕ»Ø´ðÉÏÏÂÎÄ¡£
  - planner_runtime ÔÚ specialist step ³É¹¦ºóÐ´Èë ToolContextMemory£¬ÈÃ¹¤¾ßÉó¼ÆÁ´Â·ÕæÕýÂäµØ¡£
  - ÐÂÔö pp/memory/conversation.py£¬¶Ô»á»°ÀúÊ·Ö´ÐÐÇáÁ¿Ñ¹Ëõ£º±£Áô×î½üÈô¸ÉÂÖ£¬ÆäÓàÕÛµþÎª conversation_summary¡£
  - state_rehydration¡¢wait_user¡¢eport Â·¾¶½ÓÈë»á»°Ñ¹Ëõ/ÕªÒª¶ÁÈ¡£¬¼õÉÙ³¤ÈÎÎñÉÏÏÂÎÄÅòÕÍ¡£
  - ½« 	ool_context.json Ò²µ÷ÕûÎª runtime-only ÎÄ¼þ£¬²Ö¿âÖ»±£Áô 	ool_context.example.json Ê¾Àý¡£
- Ó°Ïì·¶Î§£º
  - pp/core/answer_node.py
  - pp/orchestration/planner_runtime.py
  - pp/core/wait_user.py
  - pp/services/state_rehydration.py
  - pp/agents/report/service.py
  - pp/memory/config.py
  - pp/memory/memory_manager.py
  - pp/memory/conversation.py
  - .gitignore
  - pp/data/memory/tool_context.example.json
  - 	ests/test_phase1_multi_agent.py
- ÑéÖ¤½á¹û£º
  - python -m py_compile app/memory/config.py app/memory/memory_manager.py app/memory/conversation.py app/core/answer_node.py app/agents/report/service.py app/orchestration/planner_runtime.py app/services/state_rehydration.py app/core/wait_user.py app/core/self_reflect.py
  - pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q
  - ½á¹û£º38 passed, 1 skipped
### 2026-04-27 | Memory Convergence Follow-up | promote conversation summary into grouped task runtime
- Íê³ÉÄÚÈÝ£º
  - ½« conversation_summary Óë conversation_compacted_turns ´Ó context ¼æÈÝ×Ö¶ÎÌáÉýÎª DetectionState / TaskRuntimeState µÄÕýÊ½×Ö¶Î¡£
  - nswer_node Óë eport Â·¾¶¸ÄÎªÓÅÏÈ¶ÁÈ¡ runtime view ÖÐµÄ»á»°ÕªÒª£¬²»ÔÙÄ¬ÈÏ´Ó context È¡Öµ¡£
  - state_rehydration.restore_state() Ôö¼Ó¼æÈÝÇ¨ÒÆ£º¾É checkpoint ÈôÖ»±£´æÁË context[conversation_summary]£¬»Ö¸´Ê±»á×Ô¶¯Ó³Éäµ½ÐÂ×Ö¶Î¡£
  - pp/memory/conversation.py ¼ÌÐø±£Áô context shadow Êä³ö£¬¼æÈÝµ±Ç° API payload ÓëÇ°¶Ë¶ÁÈ¡Â·¾¶¡£
- Ó°Ïì·¶Î§£º
  - pp/memory/state.py
  - pp/memory/conversation.py
  - pp/core/answer_node.py
  - pp/agents/report/service.py
  - pp/services/state_rehydration.py
  - 	ests/test_phase1_multi_agent.py
- ÑéÖ¤½á¹û£º
  - python -m py_compile app/memory/state.py app/memory/conversation.py app/core/answer_node.py app/agents/report/service.py app/services/state_rehydration.py
  - pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q
  - ½á¹û£º38 passed, 1 skipped
### 2026-04-27 | Documentation Update | startup and debugging guide refresh
- Íê³ÉÄÚÈÝ£º
  - ¸üÐÂ README.md µÄÆô¶¯ËµÃ÷£¬²¹³ä¡°±¾µØ¿ìËÙÁªµ÷¡±ºÍ¡°ÍêÕûÔËÐÐÌ¬¡±Á½ÖÖÍÆ¼öÄ£Ê½¡£
  - ²¹³ä nomalygpt sidecar¡¢RAG ³õÊ¼»¯¡¢½¡¿µ¼ì²é¡¢OpenAPI¡¢SSE Á÷Ê½½Ó¿ÚºÍÇ°¶ËÊ±¼äÏßµÄµ÷ÊÔÂ·¾¶¡£
  - ÐÂÔö³£ÓÃ²âÊÔÃüÁîÓë³£¼ûÎÊÌâ´¦Àí£¬·½±ã°´ÎÄµµÖ±½ÓÆô¶¯ºÍÅÅÕÏ¡£
- Ó°Ïì·¶Î§£º
  - README.md
  - USER.md
- ÑéÖ¤½á¹û£º
  - ÎÄµµ¸üÐÂºó½«°´ README Êµ¼ÊÖ´ÐÐÒ»´Îºó¶ËÆô¶¯ºÍÇ°¶Ë/½Ó¿ÚÁªµ÷ÑéÖ¤¡£
### 2026-04-27 | README Smoke Verification | startup path validated on local Windows environment
- Íê³ÉÄÚÈÝ£º
  - °´ README.md Êµ¼ÊÆô¶¯ºó¶Ë²¢ÑéÖ¤ GET /health¡¢GET /openapi.json¡¢/web/index.html µÈ»ù´¡Èë¿Ú¿ÉÓÃ¡£
  - ÔÚ APP_CHECKPOINT_BACKEND=memory Ä£Ê½ÏÂ£¬Ê¹ÓÃ±¾µØ²âÊÔÍ¼Æ¬Êµ¼Ê×ßÍ¨ detect -> chat -> generate_report Ö÷Á´Â·¡£
  - ¼ÇÂ¼²¢ÐÞÕýÎÄµµÖÐµÄÁ½¸öÁªµ÷×¢Òâµã£ºWindows ÏÂ±¾µØÍÆ¼öÓÅÏÈÊ¹ÓÃ memory backend£»JSON ½Ó¿ÚÊ¾ÀýÓÅÏÈÌá¹© Invoke-RestMethod °æ±¾ÒÔ¹æ±Ü PowerShell ×ªÒåÎÊÌâ¡£
- Ó°Ïì·¶Î§£º
  - README.md
  - USER.md
- ÑéÖ¤½á¹û£º
  - GET http://127.0.0.1:8000/health
  - GET http://127.0.0.1:8000/openapi.json
  - GET http://127.0.0.1:8000/web/index.html
  - POST http://127.0.0.1:8001/v1/detect
  - POST http://127.0.0.1:8001/v1/chat
  - POST http://127.0.0.1:8001/v1/generate_report