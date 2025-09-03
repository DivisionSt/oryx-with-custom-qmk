import os
import tempfile
import pytest
from qmk_to_zmk import main as qmk_to_zmk_main

MOCK_QMK_KEYMAP_TAP_DANCE = '''
// ...existing code...
void on_dance_0(tap_dance_state_t *state, void *user_data);
void dance_0_finished(tap_dance_state_t *state, void *user_data);
void dance_0_reset(tap_dance_state_t *state, void *user_data);

enum tap_dance_codes {
    DANCE_0,
};

void on_dance_0(tap_dance_state_t *state, void *user_data) {
    if(state->count == 3) {
        tap_code16(KC_1);
        tap_code16(KC_1);
        tap_code16(KC_1);
    }
    if(state->count > 3) {
        tap_code16(KC_1);
    }
}

void dance_0_finished(tap_dance_state_t *state, void *user_data) {
    dance_state[0].step = dance_step(state);
    switch (dance_state[0].step) {
        case SINGLE_TAP: register_code16(KC_1); break;
        case SINGLE_HOLD: register_code16(KC_EXLM); break;
        case DOUBLE_TAP: register_code16(KC_F1); break;
        case DOUBLE_SINGLE_TAP: tap_code16(KC_1); register_code16(KC_1);
    }
}

void dance_0_reset(tap_dance_state_t *state, void *user_data) {
    wait_ms(10);
    switch (dance_state[0].step) {
        case SINGLE_TAP: unregister_code16(KC_1); break;
        case SINGLE_HOLD: unregister_code16(KC_EXLM); break;
        case DOUBLE_TAP: unregister_code16(KC_F1); break;
        case DOUBLE_SINGLE_TAP: unregister_code16(KC_1); break;
    }
    dance_state[0].step = 0;
}

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
  [0] = LAYOUT(
    TD(DANCE_0)
  )
};
'''

def test_tap_dance_conversion():
    with tempfile.TemporaryDirectory() as tmpdir:
        qmk_path = os.path.join(tmpdir, 'keymap.c')
        zmk_dir = os.path.join(tmpdir, 'zmk_keymap', 'config')
        os.makedirs(zmk_dir, exist_ok=True)
        with open(qmk_path, 'w') as f:
            f.write(MOCK_QMK_KEYMAP_TAP_DANCE)
        # Patch environment variables to use our temp dir for output
        import qmk_to_zmk
        qmk_to_zmk.QMK_KEYMAP_PATH = qmk_path
        qmk_to_zmk.ZMK_OUT_DIR = zmk_dir
        qmk_to_zmk.main()
        behaviors_path = os.path.join(zmk_dir, 'behaviors.dtsi')
        with open(behaviors_path) as f:
            behaviors_content = f.read()
        # Check for correct tap-dance behavior in ZMK output
    assert 'tap_dance_mod_tap_0' in behaviors_content
    assert '&mt EXCL N1' in behaviors_content or '&mt EXCL N1' in behaviors_content.replace(' ', '')
    assert '&kp F1' in behaviors_content
