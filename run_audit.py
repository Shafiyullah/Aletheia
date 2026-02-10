import ast
import os
import sys
from collections import defaultdict

EXCLUDE_DIRS = {'venv', '.git', '__pycache__', '.gemini'}
CORE_DIR = 'core'

def get_python_files(root_dir='.'):
    py_files = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))
    return py_files

class AuditVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = []
        self.definitions = []
        self.usages = []
        self.security_bypass = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.definitions.append(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.definitions.append(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.usages.append(node.id)
        self.generic_visit(node)
        
    def visit_Attribute(self, node):
        self.usages.append(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node):
        # Check for dangerous calls without security check context (Basic Heuristic)
        if isinstance(node.func, ast.Name):
            if node.func.id in ['eval', 'exec', 'subprocess']:
                self.security_bypass.append(f"Direct call to {node.func.id}")
        self.generic_visit(node)

def run_audit():
    print("Starting Architecture Audit...")
    files = get_python_files()
    
    file_stats = {}
    all_usages = set()
    global_defs = defaultdict(list)
    
    # Pass 1: Parse all files
    for f_path in files:
        with open(f_path, 'r', encoding='utf-8') as f:
            try:
                content = f.read()
                tree = ast.parse(content)
                visitor = AuditVisitor()
                visitor.visit(tree)
                
                file_stats[f_path] = {
                    'imports': visitor.imports,
                    'defs': visitor.definitions,
                    'security_issues': visitor.security_bypass
                }
                
                for u in visitor.usages:
                    all_usages.add(u)
                    
                for d in visitor.definitions:
                    global_defs[d].append(f_path)
                    
            except Exception as e:
                print(f"Error parsing {f_path}: {e}")

    # Pass 2: Analysis
    report = []
    report.append("# ARCHITECTURE AUDIT REPORT\n")
    
    # 1. Dependency Graph
    report.append("## 1. Dependency Graph")
    report.append("```mermaid")
    report.append("graph TD")
    for f, stats in file_stats.items():
        fname = os.path.basename(f)
        for imp in stats['imports']:
            if imp.startswith('core'):
                report.append(f"    {fname} --> {imp}")
    report.append("```\n")

    # 2. Dead Code Analysis
    report.append("## 2. Symbol Usage & Dead Code Analysis")
    dead_code_count = 0
    for def_name, locations in global_defs.items():
        if def_name not in all_usages and not def_name.startswith('__'):
            # Filter out streamlit lifecycle methods or common overrides if needed
            if def_name not in ['main', 'setup']: 
                report.append(f"- 🟡 **[POSSIBLE DEAD CODE]** `{def_name}` defined in `{locations[0]}` but never called.")
                dead_code_count += 1
    
    if dead_code_count == 0:
        report.append("✅ No obvious dead code found.\n")
    else:
        report.append(f"\nFound {dead_code_count} potential unused symbols.\n")

    # 3. Security Analysis
    report.append("## 3. Security Architecture")
    security_score = 100
    
    # Check if app.py imports core.safety
    app_imports = file_stats.get('.\\app.py', {}).get('imports', [])
    # Normalize path usage
    if not app_imports:
         app_imports = file_stats.get('./app.py', {}).get('imports', [])
         if not app_imports:
             # Try absolute path matching or just generic search
             for k in file_stats:
                 if k.endswith('app.py'):
                     app_imports = file_stats[k]['imports']
                     break

    if 'core.safety' in app_imports or 'core' in app_imports:
        report.append("- ✅ `app.py` correctly imports `core` security modules.")
    else:
        report.append("- 🔴 **[CRITICAL]** `app.py` does not import `core.safety`!")
        security_score -= 50

    # Check for direct dangerous calls
    issues_found = False
    for f, stats in file_stats.items():
        for issue in stats['security_issues']:
             report.append(f"- 🔴 **[SECURITY BYPASS]** {issue} in `{f}`")
             issues_found = True
             security_score -= 20
    
    if not issues_found:
        report.append("- ✅ No direct `eval/exec` calls found outside of safety checks.")

    # 4. Architecture Health
    report.append("\n## 4. Architecture Health Score")
    
    # Penalize for dead code
    health_score = max(0, security_score - (dead_code_count * 2))
    
    report.append(f"**Overall Score: {health_score}/100**")
    
    if health_score > 90:
        report.append("🟢 **EXCELLENT**")
    elif health_score > 70:
        report.append("🟡 **GOOD (Needs Cleanup)**")
    else:
        report.append("🔴 **CRITICAL ISSUES DETECTED**")

    # Output Report
    with open("ARCHITECTURE_AUDIT_REPORT.md", "w", encoding='utf-8') as f:
        f.write("\n".join(report))
    
    print("Audit Complete. Report generated.")

if __name__ == "__main__":
    run_audit()
