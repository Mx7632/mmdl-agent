# USER

## ç»´æŠ¤è§„åˆ™

- æ¯å®Œæˆä¸€ä¸ªå¯ç‹¬ç«‹éªŒæ”¶çš„æ¨¡å—ã€é˜¶æ®µæˆ–é‡è¦ä¿®å¤åï¼Œç«‹å³è¿½åŠ ä¸€æ¡è®°å½•åˆ°æœ¬æ–‡ä»¶ã€‚
- æ¯æ¡è®°å½•è‡³å°‘åŒ…å«ï¼šæ—¥æœŸã€æ¨¡å—åã€å®Œæˆå†…å®¹ã€å½±å“èŒƒå›´ã€éªŒè¯ç»“æœã€‚
- æäº¤ Git å‰ï¼Œå…ˆæ£€æŸ¥æœ¬æ–‡ä»¶æ˜¯å¦å·²åŒæ­¥æ›´æ–°ï¼›å¦‚æœæ²¡æœ‰ï¼Œéœ€è¦å…ˆè¡¥é½è®°å½•å†æäº¤ã€‚
- è¿è¡Œæ—¶äº§ç‰©ã€ä¸´æ—¶è°ƒè¯•ç»“è®ºä¸è¦å†™æˆæ­£å¼æ¨¡å—è®°å½•ï¼›åªè®°å½•å¯å¤ç°ã€å¯äº¤ä»˜çš„å¼€å‘ç»“æœã€‚

## å¼€å‘è®°å½•

### 2026-04-26 | PostgreSQL durable state ä¸ checkpoint æŒä¹…åŒ–

- å®Œæˆå†…å®¹ï¼š
  - æ–°å¢ `app/storage/postgres.py`ï¼Œå°è£… PostgreSQL è¿è¡Œæ—¶çŠ¶æ€å­˜å–ã€‚
  - æ–°å¢ `app/core/runtime.py`ï¼Œç»Ÿä¸€ç®¡ç† LangGraph checkpoint backend ä¸çº¿ç¨‹æ€åŠ è½½ã€‚
  - æ‰©å±• `app/memory/checkpoint.py`ã€`app/config/settings.py`ã€`pyproject.toml`ï¼Œæ”¯æŒ PostgreSQL æŒä¹…åŒ–é…ç½®ä¸ä¾èµ–ã€‚
  - æ‰“é€š graph state åŠ è½½ã€æŒä¹…åŒ– checkpoint ä¸åº”ç”¨çº§ runtime state é•œåƒå†™å…¥é€»è¾‘ã€‚
- å½±å“èŒƒå›´ï¼š
  - `app/core/agent.py`
  - `app/core/graph.py`
  - `app/memory/checkpoint.py`
  - `app/storage/postgres.py`
  - `app/core/runtime.py`
- éªŒè¯ç»“æœï¼š
  - `tests/test_checkpoint_store.py`
  - `tests/test_graph_runtime.py`

### 2026-04-26 | å›¾åƒæ£€æµ‹è·¯ç”±ä¸ä¸“ä¸šæ¨¡å‹æ¥å…¥

- å®Œæˆå†…å®¹ï¼š
  - æ‰©å±• `app/tools/image_anomaly_detection.py`ï¼Œæ”¯æŒé€šç”¨è§†è§‰æ¨¡å‹ä¸ä¸“ä¸šå¼‚å¸¸æ£€æµ‹åç«¯è·¯ç”±ã€‚
  - å¢åŠ ä¸“ä¸šæ¨¡å‹æœåŠ¡é…ç½®é¡¹ï¼Œå…è®¸é€šè¿‡é¡¹ç›®é…ç½®åˆ‡æ¢ `qwen` ä¸ `anomalygpt`ã€‚
  - è¡¥å……å¼‚å¸¸åŒºåŸŸå®šä½ç»“æœç»“æ„ï¼Œç»Ÿä¸€è¾“å‡ºå¼‚å¸¸åˆ—è¡¨ä¸å®šä½ä¿¡æ¯ã€‚
- å½±å“èŒƒå›´ï¼š
  - `app/tools/image_anomaly_detection.py`
  - `app/core/tools.py`
  - `app/api/main.py`
  - `app/config/settings.py`
- éªŒè¯ç»“æœï¼š
  - `tests/test_image_anomaly_detection_router.py`

### 2026-04-26 | æœ¬åœ° AnomalyGPT æœåŠ¡ä¸ Docker ä¾§è½¦

- å®Œæˆå†…å®¹ï¼š
  - æ–°å¢ `services/anomalygpt_local/` æœ¬åœ°æœåŠ¡éª¨æ¶ã€‚
  - æä¾› `Dockerfile`ã€`docker-compose.yml`ã€`start_service.ps1` ä¸æœåŠ¡è¯´æ˜æ–‡æ¡£ã€‚
  - æ”¯æŒé¡¹ç›®ä¾§é€šè¿‡ HTTP è°ƒç”¨æœ¬åœ°éƒ¨ç½²çš„ä¸“ä¸šå¼‚å¸¸æ£€æµ‹æœåŠ¡ã€‚
- å½±å“èŒƒå›´ï¼š
  - `services/anomalygpt_local/app.py`
  - `services/anomalygpt_local/Dockerfile`
  - `services/anomalygpt_local/docker-compose.yml`
  - `services/anomalygpt_local/README.md`
- éªŒè¯ç»“æœï¼š
  - æœåŠ¡æ¥çº¿ç”±ä¸»é“¾è·¯æµ‹è¯•è¦†ç›–ï¼Œé…ç½®è¯´æ˜å·²å†™å…¥é¡¹ç›®æ–‡æ¡£ã€‚

### 2026-04-26 | å‰ç«¯æ”¶æ•›ä¸ºæ ¸å¿ƒæµç¨‹é¡µ

- å®Œæˆå†…å®¹ï¼š
  - å°†å‰ç«¯æ”¶æ•›ä¸ºå•é¡µæ ¸å¿ƒæµç¨‹ï¼Œå‡å°‘åˆ†æ•£é¡µé¢ä¸é‡å¤äº¤äº’ã€‚
  - `web/index.html` è°ƒæ•´ä¸ºå›´ç»•æ£€æµ‹ã€è¿½é—®ã€æŠ¥å‘Šç”Ÿæˆçš„ä¸»å·¥ä½œæµã€‚
  - ä¿æŒåç«¯ API ä¸å˜ï¼Œå‰ç«¯ä»…åšäº¤äº’ä¸å±•ç¤ºå±‚ç®€åŒ–ã€‚
- å½±å“èŒƒå›´ï¼š
  - `web/index.html`
  - `README.md`
- éªŒè¯ç»“æœï¼š
  - `tests/test_main_flow_smoke.py`

### 2026-04-26 | å¤š Agent Phase 1ï¼šæœ‰ä¸»æ§çš„ç›‘ç£å¼æ¶æ„éª¨æ¶

- å®Œæˆå†…å®¹ï¼š
  - æ–°å¢ supervisorã€visionã€knowledgeã€report å››ç±» agent éª¨æ¶ã€‚
  - æ–°å¢ `AgentEnvelope` ä½œä¸ºä¸»æ§ä¸ä¸“å®¶ agent çš„ç»Ÿä¸€é€šä¿¡å¥‘çº¦ã€‚
  - æ‰©å±• `DetectionState`ï¼Œå¢åŠ  `agent_outputs`ã€`agent_trace`ã€`active_agent`ã€`shared_context`ã€‚
  - é‡å†™é¡¶å±‚ graphï¼Œå°†æ‰§è¡Œæµå‡çº§ä¸º supervisor è§„åˆ’ã€æ‰§è¡Œã€åˆå¹¶çš„å—æ§æµç¨‹ã€‚
  - ä¿æŒç°æœ‰å¤–éƒ¨ API ä¸å‰ç«¯åè®®ä¸å˜ï¼Œå…ˆå®Œæˆå†…éƒ¨ç¼–æ’è¿ç§»ã€‚
- å½±å“èŒƒå›´ï¼š
  - `app/agents/`
  - `app/orchestration/envelope.py`
  - `app/core/supervisor.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `app/memory/state.py`
- éªŒè¯ç»“æœï¼š
  - `tests/test_phase1_multi_agent.py`

### 2026-04-26 | ä¸»é“¾è·¯å›å½’éªŒè¯

- å®Œæˆå†…å®¹ï¼š
  - å¯¹ durable stateã€å›¾åƒè·¯ç”±ã€å¤š Agent Phase 1 ä¸ä¸»æµç¨‹è¿›è¡Œå›å½’éªŒè¯ã€‚
- éªŒè¯ç»“æœï¼š
  - æ‰§è¡Œï¼š
    - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py`
  - ç»“æœï¼š
    - `19 passed in 10.44s`

### 2026-04-26 | å·¥ä½œè®°å¿†æ–‡ä»¶æ²»ç†ï¼ˆæ–¹æ¡ˆ Bï¼‰

- å®Œæˆå†…å®¹ï¼š
  - å°† `app/data/memory/working_memory.json` å®šä¹‰ä¸ºè¿è¡Œæ—¶æ–‡ä»¶ï¼Œä¸å†çº³å…¥ Git è·Ÿè¸ªã€‚
  - æ–°å¢ `app/data/memory/working_memory.example.json` ä½œä¸ºå¯æäº¤çš„ç»“æ„æ ·ä¾‹ã€‚
  - åœ¨ `.gitignore` ä¸ `README.md` ä¸­è¡¥å……è¿è¡Œæ—¶æ–‡ä»¶ä¸æ ·ä¾‹æ–‡ä»¶çš„ä½¿ç”¨è¯´æ˜ã€‚
- å½±å“èŒƒå›´ï¼š
  - `.gitignore`
  - `README.md`
  - `app/data/memory/working_memory.example.json`
- éªŒè¯ç»“æœï¼š
  - è¿è¡Œæ—¶é€»è¾‘ä»ç„¶è¯»å–/å†™å…¥ `working_memory.json`ï¼Œä»“åº“ä¸­æ”¹ä¸ºä¿ç•™æ ·ä¾‹æ–‡ä»¶ä¾›å‚è€ƒã€‚

### 2026-04-26 | å¤š Agent Phase 2ï¼šä¸»æ§å¢å¼ºä¸ä¸‹æ¸¸çŠ¶æ€åˆ‡æ¢

- å®Œæˆå†…å®¹ï¼š
  - å°† `SupervisorAgent` ä»çº¯è§„åˆ™è·¯ç”±å‡çº§ä¸ºâ€œLLM ç»“æ„åŒ–è§„åˆ’ + è§„åˆ™å›é€€â€çš„ä¸»æ§æ¨¡å¼ã€‚
  - `supervisor_merge_node` ç°åœ¨ä¼šæŠŠ vision/knowledge/report çš„ç»“æœåŒæ­¥å› `result` ä¸ `shared_context`ï¼Œå‡å°‘å¯¹æ—§ `tool_outputs` çš„ä¾èµ–ã€‚
  - `answer_node` æ”¹ä¸ºä¼˜å…ˆæ¶ˆè´¹ `shared_context["vision"]` ä¸ `shared_context["knowledge"]`ï¼Œç¡®ä¿å›ç­”çœŸæ­£å»ºç«‹åœ¨ä¸“å®¶ Agent è¾“å‡ºä¸Šã€‚
  - æŠ¥å‘Šç”Ÿæˆé€»è¾‘ä» `app.core` è§£è€¦åˆ° `app/agents/report/service.py`ï¼Œ`ReportAgent` ä¸ graph/report å…¥å£ç»Ÿä¸€å¤ç”¨æ–°æœåŠ¡ã€‚
  - `self_reflect_node` æ”¹ä¸ºä¼˜å…ˆåŸºäºå…±äº«è§†è§‰ç»“æœè¿›è¡Œåˆ¤æ–­ï¼Œä¸æ–°çš„å¤š Agent çŠ¶æ€æµä¿æŒä¸€è‡´ã€‚
- å½±å“èŒƒå›´ï¼š
  - `app/agents/supervisor/agent.py`
  - `app/core/supervisor.py`
  - `app/core/answer_node.py`
  - `app/core/self_reflect.py`
  - `app/agents/report/service.py`
  - `app/agents/report/agent.py`
  - `app/core/graph.py`
  - `app/core/agent.py`
  - `tests/test_phase1_multi_agent.py`
- éªŒè¯ç»“æœï¼š
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - ç»“æœï¼š`22 passed`

### 2026-04-26 | å¤š Agent Phase 3ï¼šæ¾„æ¸… Agentã€å…±äº«ä¸Šä¸‹æ–‡ Schemaã€å¯ä¸­æ–­æŒ‚èµ·é“¾è·¯

- å®Œæˆå†…å®¹ï¼š
  - æ–°å¢ `ClarificationAgent`ï¼Œå½“ `self_reflect` åˆ¤æ–­éœ€è¦äººå·¥è¡¥å……æ—¶ï¼Œç”±ä¸»æ§å…ˆç”Ÿæˆç»“æ„åŒ–æ¾„æ¸…è¯·æ±‚ï¼Œå†è¿›å…¥ç­‰å¾…ç”¨æˆ·èŠ‚ç‚¹ã€‚
  - æ–°å¢ `app/orchestration/context.py`ï¼Œå°† `shared_context` ç»“æ„åŒ–ä¸º `vision/knowledge/report/clarification` å››ç±»ä¸Šä¸‹æ–‡æ¨¡å‹ã€‚
  - é‡å†™ graph è·¯ç”±ï¼Œä½¿ `wait_user` æˆä¸ºçœŸæ­£å¯ä¸­æ–­èŠ‚ç‚¹ï¼šé¦–æ¬¡æŒ‚èµ·ç›´æ¥ç»“æŸï¼Œç”¨æˆ·å›å¤åå†å›åˆ° supervisor ç»§ç»­ç¼–æ’ã€‚
  - `get_pending_task`ã€`run_detection`ã€`run_chat`ã€`continue_detection`ã€`generate_report` ç»Ÿä¸€æš´éœ² `agent_trace`ï¼Œä¾¿äºå‰ç«¯å±•ç¤ºå’Œæ’éšœã€‚
  - ä¿®æ­£ `build_continue_state` é€»è¾‘ï¼Œé¿å…ç»§ç»­æ‰§è¡Œæ—¶é‡å¤æŠŠç”¨æˆ·å›å¤ç›´æ¥å†™å…¥å†å²ï¼Œæ”¹ä¸ºäº¤ç”± `wait_user_node` æ¶ˆè´¹ã€‚
- å½±å“èŒƒå›´ï¼š
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
- éªŒè¯ç»“æœï¼š
  - `python -m pytest tests/test_phase1_multi_agent.py -q`
  - `python -m pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_image_anomaly_detection_router.py tests/test_graph_runtime.py tests/test_checkpoint_store.py -q`
  - ç»“æœï¼š`24 passed`
### 2026-04-27 | Multi-Agent Phase 4A/4B | structured execution plan + actionable retry
- å®Œæˆå†…å®¹ï¼š
  - å°† supervisor è§„åˆ’ç»“æœä»æ‰å¹³ `planned_agents` å‡çº§ä¸ºç»“æ„åŒ– `execution_plan.steps`ï¼Œæ¯ä¸ª step è®°å½• `id / agent / goal / depends_on / retryable`ã€‚
  - æ‰©å±• `DetectionState`ï¼Œæ–°å¢ `execution_plan`ã€`step_status`ã€`step_attempts`ã€`step_outputs`ã€`last_failed_step` ä»¥åŠ `retry_target / retry_reason / retry_strategy`ã€‚
  - æ”¹é€  `supervisor_plan_node` ä¸ `supervisor_execute_node`ï¼ŒæŒ‰ç»“æ„åŒ– step æ‰§è¡Œå¹¶æŠŠ step çº§çŠ¶æ€å†™å› runtime metadataã€‚
  - æ”¹é€  `self_reflect_node`ï¼Œå½“åˆ¤å®šéœ€è¦ retry æ—¶è¾“å‡ºæ˜ç¡®çš„ retry ç›®æ ‡å’Œç­–ç•¥ï¼Œä¸å†åªè¿”å›æŠ½è±¡çš„ `retry` å†³ç­–ã€‚
  - è°ƒæ•´ä¸»è¿è¡Œæ—¶è¿”å›ä¸ SSE èŠ‚ç‚¹è§‚æµ‹ï¼Œè¡¥å…… `execution_plan / step_status / step_attempts`ï¼Œå¹¶åˆ‡æ¢åˆ°çœŸå® supervisor èŠ‚ç‚¹åã€‚
  - åœ¨æ‰§è¡Œå±‚æ–°å¢æŒ‰ä¾èµ–åˆ†æ‰¹æ‰§è¡Œèƒ½åŠ›ï¼šåŒä¸€æ‰¹æ— ä¾èµ– step æ”¯æŒå¹¶å‘ï¼Œè·¨æ‰¹æ¬¡ä¿æŒé¡ºåºï¼Œä½œä¸ºåç»­æ›´å®Œæ•´ DAG ç¼–æ’çš„åŸºç¡€ã€‚
  - å°† `supervisor_merge_node` é‡æ„ä¸º agent-specific merge adaptersï¼Œé™ä½å¯¹ `vision / knowledge / clarification / report` çš„ç¡¬ç¼–ç è€¦åˆï¼Œä¸ºåç»­æ–°å¢ specialist agent é¢„ç•™ç¨³å®šæ‰©å±•ç‚¹ã€‚
  - æ–°å¢ `execution_events` æ—¶é—´çº¿ï¼Œè®°å½• `plan_created / step_started / step_completed / step_failed / task_suspended / task_resumed` ç­‰äº‹ä»¶ï¼Œå¹¶åŒæ­¥æš´éœ²åˆ° API metadataã€pending æŸ¥è¯¢ç»“æœä¸ SSE `execution_event` / `final_result.metadata`ã€‚
  - å‰ç«¯ä¸»å·¥ä½œå°æ–°å¢ multi-agent timeline é¢æ¿ï¼ŒåŸºäº `execution_plan / execution_events / step_status / step_attempts` æ¸²æŸ“ step æ¦‚è§ˆä¸äº‹ä»¶æµï¼Œå¸®åŠ©ç”¨æˆ·ç›´æ¥è§‚å¯Ÿ supervisor ç¼–æ’è¿‡ç¨‹ã€‚
  - æµå¼æ¥å£ `final_result` è¡¥å…… answer / anomalies / pending ä¿¡æ¯ï¼Œå‰ç«¯é¦–è½®æ£€æµ‹ä¸è¿½é—®åˆ‡æ¢åˆ° `/v1/stream`ï¼Œæ‰§è¡Œè¿‡ç¨‹ä¸­å¯å®æ—¶æ»šåŠ¨å±•ç¤º execution events ä¸å¢é‡å›ç­”ã€‚
  - `/v1/stream` æ–°å¢ continue åˆ†æ”¯ï¼šè¡¨å•æºå¸¦ `user_reply` æ—¶èµ°æµå¼ç»§ç»­æ¾„æ¸…é“¾è·¯ï¼Œå‰ç«¯ `continueTask()` åŒæ­¥åˆ‡æ¢ä¸ºå®æ—¶æ‰§è¡Œæ¨¡å¼ï¼Œä¸‰æ¡ä¸»è·¯å¾„ï¼ˆdetect / chat / continueï¼‰ç°å·²ç»Ÿä¸€åˆ°åŒä¸€å¥— timeline æ›´æ–°æœºåˆ¶ã€‚
- å½±å“èŒƒå›´ï¼š
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
- éªŒè¯ç»“æœï¼š
  - `pytest tests/test_phase1_multi_agent.py -q`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py -q`
  - `node` è§£æ `web/index.html` å†…è”è„šæœ¬è¯­æ³•æ£€æŸ¥
  - `pytest tests/test_main_flow_smoke.py -q`
  - ç»“æœï¼š`22 passed`ï¼Œå‰ç«¯ä¸»æµç¨‹ä¸æµå¼ continue åˆ†æ”¯é€šè¿‡

### 2026-04-27 | Frontend Timeline UX | filters, collapse, detail inspector
- Íê³ÉÄÚÈİ£º
  - Îª multi-agent timeline Ãæ°åĞÂÔö×´Ì¬É¸Ñ¡£º`È«²¿ / ÔËĞĞÖĞ / Ê§°Ü / µÈ´ı / Íê³É`£¬³¤ÈÎÎñÅÅÕÏÊ±¿ÉÒÔ¿ìËÙ¾Û½¹Òì³£ºÍ¹ÒÆğ½Úµã¡£
  - ĞÂÔö `Steps / Events` ÕÛµş¿ª¹Ø£¬ÊÂ¼şÁ÷¹ı³¤Ê±¿ÉÒÔÏÈÊÕÆğÒ»²à£¬±£Áôµ±Ç°¿´°åµÄÉ¨ÃèĞ§ÂÊ¡£
  - ĞÂÔöÏêÇéÃæ°å£¬µã»÷ step »òÊÂ¼şºó¿É²é¿´ `agent / step_id / attempt / depends_on` µÈ¹Ø¼ü×Ö¶ÎºÍÔ­Ê¼ JSON£¬·½±ã¾«È·ÅÅÕÏ¡£
  - timeline ÄÚ²¿¸ÄÎª¡°¸ÅÀÀ + ÊÂ¼şÁ÷ + ÏêÇé¼ìÊÓÆ÷¡±ÈıÀ¸½á¹¹£¬Í¬Ê±¼æÈİÒÆ¶¯¶Ëµ¥ÁĞÕ¹Ê¾¡£
- Ó°Ïì·¶Î§£º
  - `web/index.html`
- ÑéÖ¤½á¹û£º
  - `node` ½âÎö `web/index.html` ÄÚÁª½Å±¾Óï·¨¼ì²é
  - `pytest tests/test_main_flow_smoke.py tests/test_phase1_multi_agent.py tests/test_graph_runtime.py -q`
  - ½á¹û£º`22 passed`

### 2026-04-27 | Architecture Convergence Phase 1 | services split and orchestration cleanup
- Íê³ÉÄÚÈİ£º
  - ½«ÈÎÎñÔËĞĞÈë¿Ú´Ó `app/core/agent.py` ²ğ·Öµ½ `app/services/`£º·Ö±ğÂäµ½ `task_runner.py`¡¢`streaming.py`¡¢`state_rehydration.py`£¬½µµÍÔËĞĞÈë¿Ú¡¢SSE¡¢×´Ì¬»Ö¸´Ö®¼äµÄñîºÏ¡£
  - ½« supervisor ÔËĞĞÊ±´Ó `app/core/supervisor.py` ²ğ·Öµ½ `app/orchestration/`£ºĞÂÔö `planner_runtime.py`¡¢`step_executor.py`¡¢`merge_adapters.py`¡¢`events.py`¡£
  - ±£Áô `app/core/agent.py` Óë `app/core/supervisor.py` ×÷Îª¼æÈİÃÅÃæ£¬±ÜÃâÏÖÓĞ graph Óë²âÊÔµ¼ÈëÂ·¾¶Á¢¼´Ê§Ğ§¡£
  - Îª `planner / executor / consolidate / supplement` ²¹³ä legacy ±ê¼Ç£¬Ã÷È·ËüÃÇ²»ÊÇµ±Ç° supervisor Ö÷Á´Â·µÄÒ»²¿·Ö¡£
  - ĞÂÔö `Docs/architecture.md`£¬ËµÃ÷ÏÖÒÛ·Ö²ã¡¢Ö÷Á÷³Ì¡¢ÔËĞĞÈë¿Ú¡¢shared context Óë legacy Ä£¿é±ß½ç¡£
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
- Íê³ÉÄÚÈİ£º
  - ĞÂÔö `app/orchestration/context_store.py`£¬Í³Ò»¹ÜÀí `pending_clarification / pending_question / rag_context` ÕâÀàºËĞÄÒµÎñÉÏÏÂÎÄµÄ¶ÁĞ´Óë¼æÈİ shadow Í¬²½¡£
  - `merge_adapters`¡¢`wait_user`¡¢`state_rehydration`¡¢`answer_node` ¸ÄÎªÍ¨¹ı helper ·ÃÎÊ¹²ÏíÉÏÏÂÎÄ£¬¼õÉÙ `state.context[...]` µÄ·ÖÉ¢ÊÖĞ´¡£
  - ±£Áô `context` ¼æÈİ×Ö¶ÎÊä³ö£¬µ«½« `shared_context` ×÷ÎªÓÅÏÈ¶ÁÈ¡À´Ô´£¬ÎªºóĞø¼ÌĞøÊÕÁ² `context` ×ö×¼±¸¡£
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
- Íê³ÉÄÚÈİ£º
  - ÔÚ `app/memory/state.py` ÖĞĞÂÔö `TaskRuntimeState`¡¢`OrchestrationRuntimeState`¡¢`DomainRuntimeState`£¬Îª `DetectionState` Ìá¹©ÕıÊ½µÄ·Ö×éÊÓÍ¼¡£
  - ĞÂÔö `task_runtime()`¡¢`orchestration_runtime()`¡¢`domain_runtime()`£¬½«ÈÎÎñÊäÈë/»á»°¡¢±àÅÅÔËĞĞÌ¬¡¢ÁìÓò½á¹ûÉÏÏÂÎÄ°´Ö°Ôğ·Ö×éÊä³ö¡£
  - ±£³ÖÏÖÓĞ checkpoint ¶¥²ã½á¹¹²»±ä£¬ÏÈÓÃÊÓÍ¼·½Ê½ÎªºóĞø¸ü³¹µ×µÄ×´Ì¬²ğ·ÖÆÌÂ·£¬½µµÍÒ»´ÎĞÔÖØ¹¹·çÏÕ¡£
  - ÔÚ `Docs/architecture.md` ÖĞ²¹³ä state grouping ËµÃ÷£¬Ã÷È·ÕâÊÇÎ´À´×´Ì¬Ä£ĞÍÊÕÁ²µÄÇ¨ÒÆÂ·¾¶¡£
- Ó°Ïì·¶Î§£º
  - `app/memory/state.py`
  - `tests/test_phase1_multi_agent.py`
  - `Docs/architecture.md`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2C | runtime views consumed in core paths
- Íê³ÉÄÚÈİ£º
  - ½« graph Â·ÓÉÅĞ¶Ï¸ÄÎªÓÅÏÈ¶ÁÈ¡ `task_runtime()`¡¢`orchestration_runtime()`¡¢`domain_runtime()`£¬ÈÃ `execution_plan / reflection_decision / report_requested / clarification` ÕâÀà·Ö²ã±ß½çÔÚºËĞÄÁ÷³ÌÖĞÕæÕı±»Ïû·Ñ¡£
  - `self_reflect_node` ¸ÄÎªÍ¨¹ı runtime view ¶ÁÈ¡ `loop_count` Óë task parameters£¬¼õÉÙ¶Ô `DetectionState` ¶¥²ã×Ö¶ÎµÄÖ±½ÓñîºÏ¡£
  - `answer_node` ¸ÄÎªÍ¨¹ı `task_runtime()` ¶ÁÈ¡ÈÎÎñÓë»á»°ÀúÊ·£¬¿ªÊ¼°Ñ×îÖÕ»Ø´ğ½Úµã¶Ô¶¥²ã state Æ½ÃæµÄÒÀÀµÊÕÕ­¡£
  - `planner_runtime` µÄÖ´ĞĞÈë¿Ú¸ÄÎªÍ¨¹ı `orchestration_runtime()` ¶ÁÈ¡¼Æ»®Óë step Íê³ÉÌ¬£¬¸øºóĞø¸ü³¹µ×µÄ×´Ì¬²ğ·Ö¼ÌĞøÆÌÂ·¡£
- Ó°Ïì·¶Î§£º
  - `app/core/graph.py`
  - `app/core/self_reflect.py`
  - `app/core/answer_node.py`
  - `app/orchestration/planner_runtime.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`37 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2D | runtime apply helpers for write paths
- Íê³ÉÄÚÈİ£º
  - ÔÚ `DetectionState` ÖĞĞÂÔö `apply_task_runtime()`¡¢`apply_orchestration_runtime()`¡¢`apply_domain_runtime()`£¬Îª grouped runtime Ìá¹©ÕıÊ½Ğ´»ØÈë¿Ú¡£
  - `prepare_followup_state()` ¸ÄÎªÍ¨¹ı runtime apply helpers ÖØÖÃ follow-up ÂÖ´ÎËùĞè×Ö¶Î£¬¼õÉÙ¶Ô¶¥²ã state ×Ö¶ÎµÄÉ¢Ğ´¡£
  - `wait_user_node()` ¸ÄÎªÍ¨¹ı `task_runtime` / `orchestration_runtime` ¸üĞÂ»á»°¡¢¹ÒÆğ»Ö¸´ÊÂ¼şÓë `needs_user_input` ×´Ì¬£¬ÈÃ grouped runtime ¿ªÊ¼³Ğµ£Ğ´Â·¾¶Ö°Ôğ¡£
  - ĞÂÔö²âÊÔ¸²¸Ç runtime apply helpers£¬È·ÈÏ·Ö×éÊÓÍ¼²»½ö¿É¶Á£¬Ò²ÄÜÎÈ¶¨Ğ´»ØÖ÷ state¡£
- Ó°Ïì·¶Î§£º
  - `app/memory/state.py`
  - `app/services/state_rehydration.py`
  - `app/core/wait_user.py`
  - `tests/test_phase1_multi_agent.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2E | orchestration writes via grouped runtime
- Íê³ÉÄÚÈİ£º
  - `supervisor_plan_node()` Óë `supervisor_execute_node()` ¿ªÊ¼Í¨¹ı `apply_orchestration_runtime()` / `apply_domain_runtime()` »ØĞ´Ö´ĞĞ¼Æ»®¡¢step ×´Ì¬¡¢attempt¡¢step outputs Óë agent outputs¡£
  - `supervisor_merge_node()` Ïà¹Ø adapters ¿ªÊ¼Í¨¹ı grouped runtime Ğ´»Ø `tool_outputs`¡¢`shared_context`¡¢`unknown_anomaly_types` Óë `needs_user_input`£¬¼õÉÙ orchestration ²ã¶Ô `DetectionState` ¶¥²ã×Ö¶ÎµÄÉ¢Ğ´¡£
  - ²¹Æë `execution_events` ÔÚ¶¥²ã state Óë orchestration runtime ÊÓÍ¼Ö®¼äµÄÍ¬²½£¬±ÜÃâÊÂ¼ş append ºó±»¾ÉÊÓÍ¼¸²¸Ç¡£
- Ó°Ïì·¶Î§£º
  - `app/orchestration/planner_runtime.py`
  - `app/orchestration/merge_adapters.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2F | result-side writes via grouped runtime
- Íê³ÉÄÚÈİ£º
  - ÖØĞ´ `app/core/answer_node.py` Îª¸É¾»µÄ ASCII-safe ÊµÏÖ£¬²¢ÈÃ»Ø´ğ½ÚµãÍ¨¹ı `task_runtime()` / `apply_task_runtime()` Óë `domain_runtime()` ¸üĞÂ»á»°²½Êı¡¢½á¹ûÉÏÏÂÎÄÓë»Ø´ğÂäÅÌ¡£
  - ÖØĞ´ `app/agents/report/service.py` Îª¸É¾»ÊµÏÖ£¬²¢ÈÃ±¨¸æÉú³ÉÂ·¾¶Í¨¹ı grouped runtime ¶ÁÈ¡ task/orchestration/domain ĞÅÏ¢£¬×îÖÕÍ¨¹ı `apply_domain_runtime()` »ØĞ´ report ½á¹ûÓë shared context¡£
  - ÇåÀí answer/report Á½¸ö½á¹û²àºËĞÄÎÄ¼şµÄÀúÊ·±àÂëÔëÉù£¬½µµÍºóĞø¼ÌĞøÖØ¹¹Ê±µÄÓï·¨ÓëÎÄ±¾Ëğ»µ·çÏÕ¡£
- Ó°Ïì·¶Î§£º
  - `app/core/answer_node.py`
  - `app/agents/report/service.py`
- ÑéÖ¤½á¹û£º
  - `python -m py_compile app/core/answer_node.py app/agents/report/service.py`
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2G | top-level compatibility clarified and supervisor reads tightened
- Íê³ÉÄÚÈİ£º
  - Îª `DetectionState` ²¹³ä¶¥²ã×´Ì¬ËµÃ÷£¬Ã÷È· flat state ¼ÌĞø±£ÁôÓÃÓÚ checkpoint ¼æÈİ£¬µ«ĞÂ´úÂëÓ¦ÓÅÏÈ×ß grouped runtime ÊÓÍ¼¡£
  - `SupervisorAgent` ¸ÄÎªÓÅÏÈÍ¨¹ı `task_runtime()`¡¢`orchestration_runtime()`¡¢`domain_runtime()` ¶ÁÈ¡ `report_requested`¡¢`needs_user_input`¡¢`retry_*`¡¢`agent_outputs`¡¢`shared_context` µÈ¹Ø¼ü×´Ì¬¡£
  - ÈÃ supervisor ¹æ»®²ã³ÉÎª¸üÃ÷È·µÄ¡°runtime view first¡± Ïû·ÑÕß£¬¼õÉÙ¶Ô `DetectionState` ¶¥²ã×Ö¶ÎµÄÖ±½Ó¶ÁÈ¡ñîºÏ¡£
- Ó°Ïì·¶Î§£º
  - `app/memory/state.py`
  - `app/agents/supervisor/agent.py`
- ÑéÖ¤½á¹û£º
  - `pytest tests/test_phase1_multi_agent.py tests/test_main_flow_smoke.py tests/test_graph_runtime.py tests/test_agent.py -q`
  - ½á¹û£º`38 passed, 1 skipped`

### 2026-04-27 | Architecture Convergence Phase 2H | active path runtime-view-first completion
- Íê³ÉÄÚÈİ£º
  - `self_reflect`¡¢`wait_user`¡¢`step_executor`¡¢`task_runner.generate_report` µÈÊ£ÓàÏÖÒÛÄ£¿é¼ÌĞøÊÕÁ²µ½ grouped runtime ¶ÁĞ´·½Ê½¡£
  - `planner_runtime` ÖĞ agent trace µÄĞ´»ØÒ²ÄÉÈë `apply_domain_runtime()` Â·¾¶£¬¼õÉÙ active path ÉÏ¶Ô¶¥²ã state µÄÉ¢Ğ´²ĞÁô¡£
  - `Docs/architecture.md` ²¹³äÍê³ÉÌ¬ËµÃ÷£ºÏÖÒÛÖ÷Á´Â·ÒÑ¾­´ïµ½ runtime-view-first£¬¶¥²ã×Ö¶ÎÖ÷Òª³Ğµ£ checkpoint Óë¼æÈİÖ°Ôğ¡£
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
