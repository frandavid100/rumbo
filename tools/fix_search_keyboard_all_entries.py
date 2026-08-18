from pathlib import Path
p = Path('app/src/main/java/es/david/rumbo/ui/App.kt')
s = p.read_text()
old = '''    val scope = rememberCoroutineScope()
    val query = textFieldState.text.toString()
'''
new = '''    val scope = rememberCoroutineScope()
    var suppressNextExpandedKeyboard by remember { mutableStateOf(state.targetValue == SearchBarValue.Collapsed) }
    val query = textFieldState.text.toString()
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)
old = '''    LaunchedEffect(state.targetValue) {
        if (state.targetValue == SearchBarValue.Collapsed) {
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            if (textFieldState.text.isNotEmpty()) textFieldState.setTextAndPlaceCursorAtEnd("")
            onScanMessageChange(null)
            scrollBehavior.scrollOffset = 0f
            scrollBehavior.contentOffset = 0f
        }
    }
'''
new = '''    LaunchedEffect(state.targetValue) {
        if (state.targetValue == SearchBarValue.Expanded && suppressNextExpandedKeyboard) {
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            delay(300)
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            suppressNextExpandedKeyboard = false
        }
        if (state.targetValue == SearchBarValue.Collapsed) {
            suppressNextExpandedKeyboard = true
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            if (textFieldState.text.isNotEmpty()) textFieldState.setTextAndPlaceCursorAtEnd("")
            onScanMessageChange(null)
            scrollBehavior.scrollOffset = 0f
            scrollBehavior.contentOffset = 0f
        }
    }
'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new, 1)
p.write_text(s)
print('All search entry paths now open expanded without showing keyboard')
