__all__ = ["build_graph"]


def __getattr__(name: str):
    if name == "build_graph":
        from app.core.graph import build_graph

        return build_graph
    raise AttributeError(name)
