import frappe
from frappe.model.document import Document
import re

ALLOWED_OPERATORS = {'+', '-', '*', '/', '%', '(', ')'}
ALLOWED_FUNCTIONS = {'MIN', 'MAX', 'AVG', 'SUM', 'COUNT', 'IF', 'ABS', 'ROUND'}

class KPIFormula(Document):
    def validate(self):
        self.formula_code = self.formula_code.upper().strip().replace(" ", "_")
        if not re.match(r'^[A-Z][A-Z0-9_]*$', self.formula_code):
            frappe.throw("Formula Code must start with a letter and contain only uppercase letters, numbers, and underscores")
        self._validate_expression()
        self._check_circular_dependency()

    def before_save(self):
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.expression != self.expression:
                self.version = (old_doc.version or 1) + 1

    def _validate_expression(self):
        if not self.expression:
            return
        expr = self.expression.strip()
        variable_codes = {row.variable_code or row.alias for row in self.variables or [] if row.variable_code or row.alias}
        tokens = re.findall(r'[A-Z_][A-Z0-9_]*|[\d.]+|[+\-*/%(),]|\s+', expr, re.IGNORECASE)
        reconstructed = ''.join(tokens)
        if reconstructed.replace(' ', '') != expr.replace(' ', ''):
            frappe.throw(f"Formula contains invalid characters. Only variable codes, numbers, and operators (+, -, *, /, %) are allowed.")
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if re.match(r'^[\d.]+$', token):
                continue
            if token in {'+', '-', '*', '/', '%', '(', ')', ','}:
                continue
            upper_token = token.upper()
            if upper_token in ALLOWED_FUNCTIONS:
                continue
            if upper_token in variable_codes or upper_token in {v.upper() for v in variable_codes}:
                continue
            frappe.throw(f"Unknown identifier '{token}' in formula. Register it as a variable first.")

    def _check_circular_dependency(self):
        if not self.result_variable:
            return
        for row in self.variables or []:
            if row.variable == self.result_variable:
                frappe.throw(f"Circular dependency: result variable '{self.result_variable}' cannot be used as an input variable")

    @frappe.whitelist()
    def evaluate(self, values=None):
        if not self.expression:
            return None
        if values is None:
            values = {}
        expr = self.expression
        variable_map = {}
        for row in self.variables or []:
            code = row.alias or row.variable_code
            if code:
                variable_map[code.upper()] = values.get(code.upper(), values.get(row.variable, 0))
        sorted_codes = sorted(variable_map.keys(), key=len, reverse=True)
        eval_expr = expr.upper()
        for code in sorted_codes:
            val = variable_map[code]
            eval_expr = eval_expr.replace(code, str(float(val) if val else 0))
        for func_name in ALLOWED_FUNCTIONS:
            eval_expr = eval_expr.replace(func_name, func_name.lower())
        import ast
        allowed_names = {"min": min, "max": max, "abs": abs, "round": round, "sum": sum}
        try:
            tree = ast.parse(eval_expr, mode='eval')
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id not in allowed_names:
                        frappe.throw(f"Function '{node.func.id}' is not allowed")
                elif isinstance(node, ast.Name):
                    if node.id not in allowed_names:
                        frappe.throw(f"Unknown variable '{node.id}'")
            compiled = compile(tree, '<formula>', 'eval')
            result = eval(compiled, {"__builtins__": {}}, allowed_names)
            return result
        except ZeroDivisionError:
            return None
        except Exception as e:
            frappe.throw(f"Formula evaluation error: {str(e)}")
