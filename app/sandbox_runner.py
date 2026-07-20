import ast
import base64
import json
import os


ALLOWED_MODULES = {"json", "math", "statistics"}
BLOCKED_NAMES = {
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "os",
    "subprocess",
    "sys",
}


class SafetyValidator(ast.NodeVisitor):
    def visit_Attribute(self, node):
        if node.attr.startswith("_"):
            raise ValueError("Private and dunder attributes are not allowed")
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name not in ALLOWED_MODULES:
                raise ValueError(f"Module '{alias.name}' is not allowed")

    def visit_ImportFrom(self, node):
        if node.module not in ALLOWED_MODULES:
            raise ValueError(f"Module '{node.module}' is not allowed")

    def visit_Name(self, node):
        if node.id in BLOCKED_NAMES or node.id.startswith("__"):
            raise ValueError(f"Name '{node.id}' is not allowed")


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name not in ALLOWED_MODULES:
        raise ImportError(f"Module '{name}' is not allowed")
    return __import__(name, globals, locals, fromlist, level)


def main():
    code = base64.b64decode(os.environ["PYTHON_CODE_B64"]).decode()
    data = json.loads(base64.b64decode(os.environ["PYTHON_DATA_B64"]).decode())
    tree = ast.parse(code, mode="exec")
    SafetyValidator().visit(tree)

    if tree.body and isinstance(tree.body[-1], ast.Expr):
        tree.body[-1] = ast.Assign(
            targets=[ast.Name(id="result", ctx=ast.Store())],
            value=tree.body[-1].value,
        )
        ast.fix_missing_locations(tree)

    safe_builtins = {
        "__import__": safe_import,
        "abs": abs,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    scope = {"__builtins__": safe_builtins, "data": data}
    exec(compile(tree, "<agent-execution>", "exec"), scope, scope)
    if "result" in scope and scope["result"] is not None:
        print(json.dumps(scope["result"], default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
