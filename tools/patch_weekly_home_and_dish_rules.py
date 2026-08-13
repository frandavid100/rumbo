from pathlib import Path
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
t = p.read_text()
anchor = 'import androidx.compose.foundation.layout.statusBarsPadding\n'
addition = 'import androidx.compose.foundation.layout.statusBars\n'
if addition not in t:
    assert anchor in t
    t = t.replace(anchor, anchor + addition, 1)
p.write_text(t)
print('statusBars import fixed')
