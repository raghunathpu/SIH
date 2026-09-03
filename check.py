import ast
import traceback

with open("debug_output.txt", "w") as out:
    for file in ["backend/server.py", "backend/robot_agent.py"]:
        try:
            ast.parse(open(file).read(), filename=file)
            out.write(f"{file}: OK\n")
        except Exception:
            out.write(f"{file}: SYNTAX ERROR\n")
            out.write(traceback.format_exc())
            out.write("\n")
