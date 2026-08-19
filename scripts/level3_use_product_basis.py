from pathlib import Path
p = Path('app/src/main/java/es/david/rumbo/logic/CulinarySatisfactionEvaluator.kt')
text = p.read_text()
old = '''                PortionPolicyResolver.resolve(\n                    role,\n                    meal.type,\n'''
new = '''                PortionPolicyResolver.resolve(\n                    occurrence.food,\n                    role,\n                    meal.type,\n'''
if text.count(old) != 1:
    raise SystemExit(f'Esperaba una llamada al resolver, encontradas {text.count(old)}')
p.write_text(text.replace(old, new, 1))
print('Evaluador conectado a portionBasisGrams')
