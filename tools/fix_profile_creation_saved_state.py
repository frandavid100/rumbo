from pathlib import Path

p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''                    onOpenProfile = {
                        createProfileOnOpen = false
                        accountChildReturn = true
                        screenName = Screen.PROFILE.name
                    },
                    onAddProfile = {
                        createProfileOnOpen = true
                        accountChildReturn = true
                        screenName = Screen.PROFILE.name
                    },'''
new = '''                    onOpenProfile = {
                        screenStateHolder.removeState(Screen.PROFILE.name)
                        createProfileOnOpen = false
                        accountChildReturn = true
                        screenName = Screen.PROFILE.name
                    },
                    onAddProfile = {
                        screenStateHolder.removeState(Screen.PROFILE.name)
                        createProfileOnOpen = true
                        accountChildReturn = true
                        screenName = Screen.PROFILE.name
                    },'''
if s.count(old) != 1:
    raise SystemExit(f'expected one account profile navigation block, found {s.count(old)}')
p.write_text(s.replace(old, new, 1))
print('Profile screen saveable state reset for edit/create navigation')
