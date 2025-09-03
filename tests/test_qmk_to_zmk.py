import os
import tempfile
import pytest
from qmk_to_zmk import main as qmk_to_zmk_main

MOCK_QMK_KEYMAP = '''
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
  [0] = LAYOUT(
    KC_A
  )
};
'''

def test_simple_kc_a_conversion():
    with tempfile.TemporaryDirectory() as tmpdir:
        qmk_path = os.path.join(tmpdir, 'keymap.c')
        zmk_path = os.path.join(tmpdir, 'keymap.keymap')
        with open(qmk_path, 'w') as f:
            f.write(MOCK_QMK_KEYMAP)
        # Assume the script takes input and output file arguments
        qmk_to_zmk_main([qmk_path, zmk_path])
        with open(zmk_path) as f:
            zmk_content = f.read()
        assert 'A' in zmk_content, f"Expected 'A' in output, got: {zmk_content}"
