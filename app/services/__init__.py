from app.services.task_runner import continue_detection, generate_report, get_pending_task, run_chat, run_detection


async def stream_continue_detection(*args, **kwargs):
    from app.services.streaming import stream_continue_detection as impl

    async for item in impl(*args, **kwargs):
        yield item


async def stream_detection(*args, **kwargs):
    from app.services.streaming import stream_detection as impl

    async for item in impl(*args, **kwargs):
        yield item

__all__ = [
    "continue_detection",
    "generate_report",
    "get_pending_task",
    "run_chat",
    "run_detection",
    "stream_continue_detection",
    "stream_detection",
]
