from pathlib import Path
import re

files = [
    Path('app/src/test/java/es/david/rumbo/logic/MenuConstraintContractTest.kt'),
    Path('app/src/test/java/es/david/rumbo/logic/RepertoireEvaluatorTest.kt'),
    Path('app/src/test/java/es/david/rumbo/logic/MenuProgressDiagnosticsTest.kt'),
]
for p in files:
    s=p.read_text()
    if 'CulinaryType' in s:
        s=s.replace('import es.david.rumbo.model.CulinaryType\n','import es.david.rumbo.model.legacyCulinaryRoles\n')
        s=re.sub(
            r'culinaryType\s*=\s*CulinaryType\.([A-Z_]+)',
            r'culinaryRoles = legacyCulinaryRoles("\1")',
            s
        )
        if 'CulinaryType' in s:
            raise SystemExit(f'unmigrated CulinaryType in {p}')
    p.write_text(s)

p=Path('app/src/test/java/es/david/rumbo/logic/WeeklyMenuGeneratorTest.kt')
s=p.read_text()
s=s.replace('import es.david.rumbo.model.CulinaryType\n','import es.david.rumbo.model.legacyCulinaryRoles\n')
s=s.replace('''        culinaryType: CulinaryType = CulinaryType.UNKNOWN
''','''        legacyTypeName: String? = null
''')
s=s.replace('''        culinaryType = culinaryType
''','''        culinaryRoles = legacyCulinaryRoles(legacyTypeName)
''')
s=re.sub(r'CulinaryType\.([A-Z_]+)', r'"\1"', s)
s=s.replace('CulinaryRole.STARCH_BASE','CulinaryRole.PLATE_BASE')
s=s.replace('CulinaryRole.PRIMARY_PROTEIN','CulinaryRole.PLATE_CENTER')
if 'CulinaryType' in s: raise SystemExit('unmigrated CulinaryType in WeeklyMenuGeneratorTest')
p.write_text(s)

print('Legacy culinary test fixtures migrated to role sets')
