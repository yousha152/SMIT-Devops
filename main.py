from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json
from datetime import datetime
import ast
import operator


app = FastAPI(title="Orange Black Calculator")

templates = Jinja2Templates(directory="templates")

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "history.json"


def load_history():
    if not DB_FILE.exists():
        DB_FILE.write_text("[]", encoding="utf-8")

    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history):
    DB_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# Safe arithmetic evaluator
# Supports: +, -, *, /, %, // and **
# Does NOT use eval()

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
}

UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_calculate(expression: str):
    expression = expression.strip()

    if not expression:
        raise ValueError("Please enter an expression.")

    if len(expression) > 100:
        raise ValueError("Expression is too long.")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError("Invalid expression.")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)

        if isinstance(node, ast.Constant) and isinstance(
            node.value, (int, float)
        ):
            return node.value

        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPS:
            return UNARY_OPS[type(node.op)](
                evaluate(node.operand)
            )

        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            left = evaluate(node.left)
            right = evaluate(node.right)

            # Prevent extremely large exponent calculations
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent is too large.")

            return BIN_OPS[type(node.op)](left, right)

        raise ValueError(
            "Only basic arithmetic operations are allowed."
        )

    result = evaluate(tree)

    if isinstance(result, float) and result.is_integer():
        return int(result)

    return result


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    history = load_history()

    current_result = history[0]["result"] if history else None

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "history": history,
            "current_result": current_result
        }
    )


@app.post("/calculate", response_class=HTMLResponse)
async def calculate(
    request: Request,
    expression: str = Form(...)
):
    history = load_history()

    try:
        result = safe_calculate(expression)

        item = {
            "expression": expression.strip(),
            "result": str(result),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        history.insert(0, item)

        # Keep only latest 50 calculations
        history = history[:50]

        save_history(history)

    except (ValueError, ZeroDivisionError, OverflowError) as error:
        current_result = history[0]["result"] if history else None

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "history": history,
                "error": str(error),
                "expression": expression,
                "current_result": current_result
            },
            status_code=400
        )

    return RedirectResponse("/", status_code=303)


@app.post("/clear")
async def clear_history():
    save_history([])

    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
