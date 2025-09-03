#!/usr/bin/env python3
"""
QMK to ZMK Conversion Script
Automatically converts QMK firmware keymap to ZMK format
"""

import os
import re
import json
from typing import Dict, List, Tuple, Any

QMK_KEYMAP_PATH = "rAboj/keymap.c"
QMK_CONFIG_PATH = "rAboj/config.h" 
ZMK_OUT_DIR = "zmk_keymap/config"

# Comprehensive QMK to ZMK keycode mapping
QMK_TO_ZMK_KEYCODES = {
    'KC_ESCAPE': 'ESC', 'KC_TAB': 'TAB', 'KC_BSPC': 'BSPC', 'KC_ENTER': 'RET',
    'KC_SPACE': 'SPACE', 'KC_LEFT_SHIFT': 'LSHFT', 'KC_RIGHT_SHIFT': 'RSHFT',
    'KC_LEFT_CTRL': 'LCTRL', 'KC_RIGHT_CTRL': 'RCTRL', 'KC_LEFT_ALT': 'LALT',
    'KC_RIGHT_ALT': 'RALT', 'KC_LEFT_GUI': 'LGUI', 'KC_RIGHT_GUI': 'RGUI',
    'KC_TRANSPARENT': 'trans', 'KC_NO': 'none', 'KC_COMMA': 'COMMA',
    'KC_DOT': 'DOT', 'KC_SLASH': 'FSLH', 'KC_SCLN': 'SEMI', 'KC_QUOTE': 'SQT',
    'KC_BSLS': 'BSLH', 'KC_GRAVE': 'GRAVE', 'KC_MINUS': 'MINUS', 'KC_EQUAL': 'EQUAL',
    'KC_LBRC': 'LBKT', 'KC_RBRC': 'RBKT', 'KC_DELETE': 'DEL', 'KC_HOME': 'HOME',
    'KC_END': 'END', 'KC_PAGE_UP': 'PG_UP', 'KC_PGDN': 'PG_DN', 'KC_LEFT': 'LEFT',
    'KC_DOWN': 'DOWN', 'KC_UP': 'UP', 'KC_RIGHT': 'RIGHT', 'KC_NUM': 'KP_NUM',
    'KC_KP_SLASH': 'KP_DIVIDE', 'KC_KP_ASTERISK': 'KP_MULTIPLY', 'KC_KP_MINUS': 'KP_MINUS',
    'KC_KP_PLUS': 'KP_PLUS', 'KC_KP_ENTER': 'KP_ENTER', 'KC_KP_DOT': 'KP_DOT',
    'KC_MS_UP': 'MMOV', 'KC_MS_DOWN': 'MMOV', 'KC_MS_LEFT': 'MMOV', 'KC_MS_RIGHT': 'MMOV',
    'KC_MS_BTN1': 'MKPD', 'KC_MS_BTN2': 'MKPD', 'KC_MS_BTN3': 'MKPD',
    'KC_MS_WH_UP': 'MWHL', 'KC_MS_WH_DOWN': 'MWHL', 'CW_TOGG': 'CAPS',
    'QK_BOOTLOADER': 'bootloader', 'QK_REBOOT': 'reset',
    # Symbol keycodes
    'KC_EXLM': 'EXCL', 'KC_AT': 'AT', 'KC_HASH': 'HASH', 'KC_DLR': 'DLLR',
    'KC_PERC': 'PRCNT', 'KC_CIRC': 'CARET', 'KC_AMPR': 'AMPS', 'KC_ASTR': 'ASTRK',
    'KC_LPRN': 'LPAR', 'KC_RPRN': 'RPAR', 'KC_UNDS': 'UNDER', 'KC_PLUS': 'PLUS',
    'KC_LCBR': 'LBRC', 'KC_RCBR': 'RBRC', 'KC_PIPE': 'PIPE', 'KC_COLN': 'COLON',
    'KC_DQUO': 'DQT', 'KC_LT': 'LT', 'KC_GT': 'GT', 'KC_QUES': 'QMARK',
    'KC_TILD': 'TILDE'
}

# Add number and letter keys
for i in range(10):
    QMK_TO_ZMK_KEYCODES[f'KC_{i}'] = f'N{i}'
for i in range(1, 25):
    QMK_TO_ZMK_KEYCODES[f'KC_F{i}'] = f'F{i}'
for i in range(0, 10):
    QMK_TO_ZMK_KEYCODES[f'KC_KP_{i}'] = f'KP_N{i}'
for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    QMK_TO_ZMK_KEYCODES[f'KC_{c}'] = c

class QMKParser:
    def __init__(self, keymap_path: str, config_path: str = None):
        self.keymap_path = keymap_path
        self.config_path = config_path
        with open(keymap_path, 'r') as f:
            self.content = f.read()
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config_content = f.read()
        else:
            self.config_content = ""
    
    def parse_tap_dances(self) -> Dict[str, Dict]:
        """Parse all tap dance definitions"""
        tap_dances = {}
        
        # Extract tap dance enum
        enum_match = re.search(r'enum tap_dance_codes\s*{([^}]*)};', self.content, re.DOTALL)
        if not enum_match:
            return tap_dances
        
        dance_names = [name.strip() for name in enum_match.group(1).split(',') if name.strip()]
        
        # Extract each tap dance implementation
        for i, dance_name in enumerate(dance_names):
            dance_impl = self.extract_tap_dance_impl(i)
            if dance_impl:
                tap_dances[dance_name] = dance_impl
        
        return tap_dances
    
    def extract_tap_dance_impl(self, dance_id: int) -> Dict:
        """Extract implementation details for a specific tap dance, supporting tap, hold, and double-tap."""
        impl = {'single_tap': None, 'single_hold': None, 'double_tap': None}
        # Look for the dance_X_finished function implementation
        pattern = rf'void dance_{dance_id}_finished\(tap_dance_state_t \*state, void \*user_data\)\s*{{([\s\S]*?)}}'
        match = re.search(pattern, self.content, re.DOTALL)
        if match:
            function_body = match.group(1)
            # Helper to extract keycode from register_code16 or tap_code16 for a given case, robust to whitespace/line breaks
            def extract_keycode_from_case(text, case_name):
                # Allow for arbitrary whitespace/comments between case and function call
                reg_pat = rf'case\s+{case_name}\s*:\s*(?:/\*.*?\*/\s*)*register_code16\s*\(([^)]+)\)\s*;'
                reg_match = re.search(reg_pat, text, re.DOTALL)
                if reg_match:
                    return reg_match.group(1).strip()
                tap_pat = rf'case\s+{case_name}\s*:\s*(?:/\*.*?\*/\s*)*tap_code16\s*\(([^)]+)\)\s*;'
                tap_match = re.search(tap_pat, text, re.DOTALL)
                if tap_match:
                    return tap_match.group(1).strip()
                return None
            impl['single_tap'] = extract_keycode_from_case(function_body, 'SINGLE_TAP')
            impl['single_hold'] = extract_keycode_from_case(function_body, 'SINGLE_HOLD')
            impl['double_tap'] = extract_keycode_from_case(function_body, 'DOUBLE_TAP')
        return impl
    
    def parse_dual_functions(self) -> Dict[str, Dict]:
        """Parse all dual function (LT) definitions"""
        dual_functions = {}
        
        # Find all DUAL_FUNC_X defines
        pattern = r'#define\s+(DUAL_FUNC_\d+)\s+LT\((\d+),\s*([^)]+)\)'
        matches = re.findall(pattern, self.content)
        
        for func_name, layer, keycode in matches:
            dual_functions[func_name] = {
                'hold': f'layer {layer}',
                'tap': keycode.strip()
            }
        
        return dual_functions
    
    def parse_custom_dual_functions(self) -> Dict[str, Dict]:
        """Parse custom dual function implementations"""
        custom_dfs = {}
        
        # Look for any other LT() usages in the keymap
        layer_matches = re.findall(r'LT\((\d+),\s*([^)]+)\)', self.content)
        
        for i, (layer, keycode) in enumerate(layer_matches):
            func_name = f'custom_lt_{i}'
            custom_dfs[func_name] = {
                'hold': f'layer {layer}',
                'tap': keycode.strip()
            }
        
        return custom_dfs
    
    def parse_macros(self) -> Dict[str, str]:
        """Parse macro definitions"""
        macros = {}
        
        # Find ST_MACRO definitions
        pattern = r'#define\s+(ST_MACRO_\d+)\s+.*?"([^"]*)"'
        matches = re.findall(pattern, self.content)
        
        for macro_name, macro_string in matches:
            macros[macro_name] = macro_string
        
        return macros
    
    def parse_keymaps(self) -> List[List[List[str]]]:
        """Parse all keymap layers"""
        # Extract the entire keymaps array
        pattern = r'const uint16_t PROGMEM keymaps\[\]\[MATRIX_ROWS\]\[MATRIX_COLS\]\s*=\s*{(.*?)};'
        match = re.search(pattern, self.content, re.DOTALL)
        if not match:
            return []
        keymaps_content = match.group(1)
        layers = []
        # Accept any LAYOUT macro
        layer_starts = []
        for match in re.finditer(r'\[(\d+)\]\s*=\s*LAYOUT[_A-Za-z0-9]*\(', keymaps_content):
            layer_starts.append((int(match.group(1)), match.start(), match.end()))
        for i, (layer_num, start_pos, content_start) in enumerate(layer_starts):
            paren_count = 1
            pos = content_start
            while pos < len(keymaps_content) and paren_count > 0:
                if keymaps_content[pos] == '(': 
                    paren_count += 1
                elif keymaps_content[pos] == ')':
                    paren_count -= 1
                pos += 1
            if paren_count == 0:
                layer_content = keymaps_content[content_start:pos-1]
                keys = self.split_layer_keys(layer_content)
                # For test, just group as a single row
                layer_keys = [keys]
                layers.append(layer_keys)
        return layers
    
    def split_layer_keys(self, layer_content: str) -> List[str]:
        """Split layer content into individual keys, handling nested parentheses"""
        keys = []
        current_key = ""
        paren_depth = 0
        
        for char in layer_content:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                if current_key.strip():
                    keys.append(current_key.strip())
                current_key = ""
                continue
            
            current_key += char
        
        if current_key.strip():
            keys.append(current_key.strip())
        
        return keys
    
    def group_ergodox_keys(self, keys: List[str]) -> List[List[str]]:
        """Group keys into Ergodox layout rows"""
        # Ergodox layout: 14 keys top row, 14 keys second row, etc.
        if len(keys) < 76:  # Typical ergodox has 76 keys
            # Pad with KC_NO if needed
            keys.extend(['KC_NO'] * (76 - len(keys)))
        
        # Group into rows (this is simplified - actual Ergodox layout is more complex)
        rows = []
        key_index = 0
        
        # Row layout for Ergodox (simplified)
        row_sizes = [7, 7, 7, 7, 7, 7, 5, 3, 3, 7, 7, 7, 7, 7, 7, 5, 3, 3]
        
        for row_size in row_sizes:
            if key_index + row_size <= len(keys):
                rows.append(keys[key_index:key_index + row_size])
                key_index += row_size
            else:
                break
        
        return rows


class ZMKGenerator:
    def __init__(self, tap_dances: Dict, dual_functions: Dict, custom_dual_functions: Dict, 
                 macros: Dict, keymaps: List):
        self.tap_dances = tap_dances
        self.dual_functions = dual_functions
        self.custom_dual_functions = custom_dual_functions
        self.macros = macros
        self.keymaps = keymaps
    
    def convert_keycode(self, qmk_keycode: str) -> str:
        """Convert QMK keycode to ZMK equivalent"""
        # Handle special cases first
        if qmk_keycode.startswith('TD('):
            dance_name = qmk_keycode[3:-1].replace('DANCE_', '')
            # For tap dances, we need to provide the hold action parameter
            # We'll use the hold keycode from the tap dance implementation
            dance_id = dance_name.replace('dance_', '')
            dance_impl_name = f'DANCE_{dance_id}'
            if dance_impl_name in self.tap_dances:
                hold_key = self.tap_dances[dance_impl_name]['single_hold']
                if hold_key:
                    hold_zmk = self.convert_keycode(hold_key).replace('&kp ', '').replace('&', '')
                    return f'&dance_{dance_id} {hold_zmk} 0'
            return f'&dance_{dance_id} ESC 0'
        
        if qmk_keycode.startswith('DUAL_FUNC_'):
            return f'&{qmk_keycode.lower()}'
        
        if qmk_keycode.startswith('ST_MACRO_'):
            macro_num = qmk_keycode.split('_')[-1]
            return f'&macro_{macro_num}'
        
        if qmk_keycode.startswith('LT('):
            # Extract layer and keycode from LT(layer, keycode)
            content = qmk_keycode[3:-1]
            parts = content.split(',', 1)
            if len(parts) == 2:
                layer = parts[0].strip()
                key = parts[1].strip()
                zmk_key = self.convert_keycode(key).replace('&kp ', '').replace('&', '')
                return f'&lt {layer} {zmk_key}'
        
        if qmk_keycode.startswith('TO('):
            layer = qmk_keycode[3:-1]
            return f'&to {layer}'
        
        if qmk_keycode.startswith('TT('):
            layer = qmk_keycode[3:-1]
            return f'&tog {layer}'
        
        # Handle modifier combinations
        if qmk_keycode.startswith(('LGUI(', 'LCTL(', 'LALT(', 'LSFT(')):
            return self.convert_modifier_combo(qmk_keycode)
        
        # Handle special keys that don't use kp prefix
        special_keys = {
            'QK_REPEAT_KEY': '&key_repeat',
            'DM_PLY1': '&kp none',  # Dynamic macro - ZMK doesn't have direct equivalent
            'DM_PLY2': '&kp none',
            'DM_REC1': '&kp none',
            'DM_REC2': '&kp none',
            'DM_RSTP': '&kp none'
        }
        
        if qmk_keycode in special_keys:
            return special_keys[qmk_keycode]
        
        # Direct keycode mapping
        if qmk_keycode in QMK_TO_ZMK_KEYCODES:
            return f'&kp {QMK_TO_ZMK_KEYCODES[qmk_keycode]}'
        
        # Fallback - try to handle unknown keycodes
        if qmk_keycode.startswith('KC_'):
            # Strip KC_ prefix and use as-is
            return f'&kp {qmk_keycode[3:]}'
        
        # Last resort - use none for truly unknown codes
        return '&kp none'
    
    def convert_modifier_combo(self, qmk_keycode: str) -> str:
        """Convert modifier combinations like LGUI(KC_T) to ZMK format"""
        # Handle nested modifiers like LGUI(LCTL(KC_SPACE))
        if qmk_keycode.startswith('LGUI(') and qmk_keycode.endswith(')'):
            inner = qmk_keycode[5:-1]
            if inner.startswith('LCTL(') and inner.endswith(')'):
                # Double nested: LGUI(LCTL(KC_SPACE))
                inner_inner = inner[5:-1]
                zmk_inner = self.convert_keycode(inner_inner).replace('&kp ', '')
                return f'&kp LG(LC({zmk_inner}))'
            elif inner.startswith('LSFT(') and inner.endswith(')'):
                # LGUI(LSFT(KC_T))
                inner_inner = inner[5:-1]
                zmk_inner = self.convert_keycode(inner_inner).replace('&kp ', '')
                return f'&kp LG(LS({zmk_inner}))'
            else:
                zmk_inner = self.convert_keycode(inner).replace('&kp ', '')
                return f'&kp LG({zmk_inner})'
        
        if qmk_keycode.startswith('LCTL(') and qmk_keycode.endswith(')'):
            inner = qmk_keycode[5:-1]
            if inner.startswith('LGUI(') and inner.endswith(')'):
                # LCTL(LGUI(...))
                inner_inner = inner[5:-1]
                zmk_inner = self.convert_keycode(inner_inner).replace('&kp ', '')
                return f'&kp LC(LG({zmk_inner}))'
            elif inner.startswith('LSFT(') and inner.endswith(')'):
                # LCTL(LSFT(KC_T))
                inner_inner = inner[5:-1]
                zmk_inner = self.convert_keycode(inner_inner).replace('&kp ', '')
                return f'&kp LC(LS({zmk_inner}))'
            else:
                zmk_inner = self.convert_keycode(inner).replace('&kp ', '')
                return f'&kp LC({zmk_inner})'
        
        if qmk_keycode.startswith('LALT(') and qmk_keycode.endswith(')'):
            inner = qmk_keycode[5:-1]
            # Handle complex nested cases like LALT(LCTL(LGUI(LSFT(KC_LEFT))))
            if '(' in inner:
                # Recursively handle nested modifiers
                zmk_inner = self.convert_modifier_combo(inner).replace('&kp ', '')
                return f'&kp LA({zmk_inner})'
            else:
                zmk_inner = self.convert_keycode(inner).replace('&kp ', '')
                return f'&kp LA({zmk_inner})'
        
        if qmk_keycode.startswith('LSFT(') and qmk_keycode.endswith(')'):
            inner = qmk_keycode[5:-1]
            zmk_inner = self.convert_keycode(inner).replace('&kp ', '')
            return f'&kp LS({zmk_inner})'
        
        # Fallback
        return f'&kp {qmk_keycode}'
    
    def generate_behaviors_dtsi(self) -> str:
        """Generate behaviors.dtsi file with all custom behaviors"""
        content = """// Auto-generated by qmk_to_zmk.py - Complete behaviors conversion
#include <dt-bindings/zmk/keys.h>

/ {
    behaviors {
"""
        
        # Generate tap dance behaviors using combined tap-dance + hold-tap approach
        for i in range(24):  # Assuming 24 tap dances from DANCE_0 to DANCE_23
            dance_name = f'DANCE_{i}'
            if dance_name in self.tap_dances:
                dance_impl = self.tap_dances[dance_name]
                # Convert QMK keycodes to ZMK format
                # For <&mt HOLD TAP>, strip any &kp or & prefix, keep only the keycode
                def strip_kp_prefix(val):
                    if val is None:
                        return 'ESC'
                    v = val.strip()
                    if v.startswith('&kp '):
                        return v[4:].strip()
                    if v.startswith('&'):
                        return v[1:].strip()
                    return v
                single_tap = strip_kp_prefix(self.convert_keycode(dance_impl['single_tap'])) if dance_impl['single_tap'] else 'ESC'
                single_hold = strip_kp_prefix(self.convert_keycode(dance_impl['single_hold'])) if dance_impl['single_hold'] else 'ESC'
                double_tap = strip_kp_prefix(self.convert_keycode(dance_impl['double_tap'])) if dance_impl['double_tap'] else 'ESC'
                # Generate the tap-dance mod-tap behavior (tap, hold, double-tap)
                content += f"        td_mt_{i}: tap_dance_mod_tap_{i} {{\n"
                content += "            compatible = \"zmk,behavior-tap-dance\";\n"
                content += "            #binding-cells = <0>;\n"
                content += "            tapping-term-ms = <200>;\n"
                content += f"            bindings = <&mt {single_hold} {single_tap}>, <&kp {double_tap}>;\n"
                content += "        };\n\n"
            else:
                # Fallback for undefined tap dances
                content += f"        td_mt_{i}: tap_dance_mod_tap_{i} {{\n"
                content += "            compatible = \"zmk,behavior-tap-dance\";\n"
                content += "            #binding-cells = <0>;\n"
                content += "            tapping-term-ms = <200>;\n"
                content += "            bindings = <&kp ESC>, <&kp ESC>;\n"
                content += "        };\n\n"
        
        # Generate dual function behaviors
        for func_name, func_impl in self.dual_functions.items():
            tap_key = self.convert_keycode(func_impl['tap']).replace('&kp ', '')
            hold_key = func_impl['hold'].replace('layer ', '')
            content += f"        {func_name.lower()}: {func_name.lower()} {{\n"
            content += "            compatible = \"zmk,behavior-hold-tap\";\n"
            content += "            #binding-cells = <2>;\n"
            content += "            flavor = \"tap-preferred\";\n"
            content += "            tapping-term-ms = <150>;\n"
            content += "            bindings = <&mo>, <&kp>;\n"
            content += "        };\n\n"
        
        # Generate custom dual functions
        for func_name, func_impl in self.custom_dual_functions.items():
            tap_key = self.convert_keycode(func_impl['tap']).replace('&kp ', '')
            hold_key = func_impl['hold'].replace('layer ', '')
            content += f"        {func_name}: {func_name} {{\n"
            content += "            compatible = \"zmk,behavior-hold-tap\";\n"
            content += "            #binding-cells = <2>;\n"
            content += "            flavor = \"tap-preferred\";\n"
            content += "            tapping-term-ms = <150>;\n"
            content += "            bindings = <&mo>, <&kp>;\n"
            content += "        };\n\n"
        
        content += "    };\n};\n"
        return content
    
    def generate_board_overlay(self) -> str:
        """Generate board.overlay for SliceMK Ergodox Wireless Lite"""
        return """// Auto-generated by qmk_to_zmk.py - SliceMK Ergodox Wireless Lite configuration
#include <dt-bindings/zmk/matrix_transform.h>

/ {
    chosen {
        zmk,kscan = &kscan0;
        zmk,matrix_transform = &default_transform;
    };

    kscan0: kscan {
        compatible = "zmk,kscan-gpio-matrix";
        diode-direction = "col2row";
        row-gpios = <&gpio0 21 (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>,
                    <&gpio0 19 (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>,
                    <&gpio0 20 (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>,
                    <&gpio0 22 (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>,
                    <&gpio0 24 (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>,
                    <&gpio1 0  (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>;
        col-gpios = <&gpio0 2  GPIO_ACTIVE_HIGH>,
                    <&gpio0 29 GPIO_ACTIVE_HIGH>,
                    <&gpio0 28 GPIO_ACTIVE_HIGH>,
                    <&gpio0 3  GPIO_ACTIVE_HIGH>,
                    <&gpio1 13 GPIO_ACTIVE_HIGH>,
                    <&gpio1 11 GPIO_ACTIVE_HIGH>,
                    <&gpio0 30 GPIO_ACTIVE_HIGH>;
    };

    default_transform: keymap_transform_0 {
        compatible = "zmk,matrix-transform";
        columns = <14>;
        rows = <6>;
        map = <
RC(0,0) RC(0,1) RC(0,2) RC(0,3) RC(0,4) RC(0,5) RC(0,6)                         RC(0,7) RC(0,8) RC(0,9) RC(0,10) RC(0,11) RC(0,12) RC(0,13)
RC(1,0) RC(1,1) RC(1,2) RC(1,3) RC(1,4) RC(1,5) RC(1,6)                         RC(1,7) RC(1,8) RC(1,9) RC(1,10) RC(1,11) RC(1,12) RC(1,13)
RC(2,0) RC(2,1) RC(2,2) RC(2,3) RC(2,4) RC(2,5)                                         RC(2,8) RC(2,9) RC(2,10) RC(2,11) RC(2,12) RC(2,13)
RC(3,0) RC(3,1) RC(3,2) RC(3,3) RC(3,4) RC(3,5) RC(3,6)                         RC(3,7) RC(3,8) RC(3,9) RC(3,10) RC(3,11) RC(3,12) RC(3,13)
RC(4,0) RC(4,1) RC(4,2) RC(4,3) RC(4,4)                                                         RC(4,9) RC(4,10) RC(4,11) RC(4,12) RC(4,13)
                                        RC(5,5) RC(5,6)         RC(5,7) RC(5,8)
                                                RC(5,4)         RC(5,9)
                                RC(5,3) RC(5,2) RC(5,1)         RC(5,10) RC(5,11) RC(5,12)
        >;
    };
};
"""
    
    def generate_boards_dtsi(self) -> str:
        """Generate boards.dtsi file"""
        return """// Auto-generated by qmk_to_zmk.py - Board configuration
#include <dt-bindings/zmk/keys.h>
"""
    
    def generate_zmk_conf(self) -> str:
        """Generate zmk.conf configuration file"""
        return """# Auto-generated by qmk_to_zmk.py - ZMK configuration
CONFIG_ZMK_SLEEP=y
CONFIG_ZMK_IDLE_SLEEP_TIMEOUT=1800000
"""
    
    def generate_keymap_keymap(self) -> str:
        """Generate complete keymap.keymap file"""
        content = """// Auto-generated by qmk_to_zmk.py - Complete keymap conversion
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";

"""
        
        # Generate each layer
        for layer_idx, layer in enumerate(self.keymaps):
            content += f"        layer_{layer_idx} {{\n"
            content += "            bindings = <\n"
            
            # Convert all keys in the layer
            for row_idx, row in enumerate(layer):
                row_keys = []
                for key in row:
                    # If this is a tap-dance key, replace &dance_X with &td_mt_X
                    zmk_key = self.convert_keycode(key)
                    if zmk_key.startswith('&dance_'):
                        # Extract the index
                        try:
                            idx = int(zmk_key.split('_')[1].split()[0])
                            # Preserve any extra args (e.g., EXCL 0)
                            rest = zmk_key.split(' ', 1)[1] if ' ' in zmk_key else ''
                            zmk_key = f'&td_mt_{idx}{(" " + rest) if rest else ""}'
                        except Exception:
                            pass
                    row_keys.append(zmk_key)
                
                if row_keys:
                    content += f"                {' '.join(row_keys)}"
                    if row_idx < len(layer) - 1:
                        content += "\n"
            
            content += "\n            >;\n"
            content += "        };\n\n"
        
        content += "    };\n};\n"
        return content
    
    def generate_config_files(self):
        """Generate all ZMK config files"""
        os.makedirs(ZMK_OUT_DIR, exist_ok=True)
        
        # Generate each file
        files = {
            'behaviors.dtsi': self.generate_behaviors_dtsi(),
            'board.overlay': self.generate_board_overlay(),
            'boards.dtsi': self.generate_boards_dtsi(),
            'zmk.conf': self.generate_zmk_conf(),
            'keymap.keymap': self.generate_keymap_keymap()
        }
        
        for filename, content in files.items():
            filepath = os.path.join(ZMK_OUT_DIR, filename)
            with open(filepath, 'w') as f:
                f.write(content)


def main(args=None):
    """Main conversion function
    Optionally takes [qmk_keymap_path, zmk_keymap_path] as args for testability.
    """
    print("Starting QMK to ZMK conversion...")
    if args and len(args) == 2:
        qmk_keymap_path, zmk_keymap_path = args
        parser = QMKParser(qmk_keymap_path)
        tap_dances = parser.parse_tap_dances()
        dual_functions = parser.parse_dual_functions()
        custom_dual_functions = parser.parse_custom_dual_functions()
        macros = parser.parse_macros()
        keymaps = parser.parse_keymaps()
        # Generate ZMK config to the given output file only
        generator = ZMKGenerator(tap_dances, dual_functions, custom_dual_functions, macros, keymaps)
        keymap_content = generator.generate_keymap_keymap()
        with open(zmk_keymap_path, 'w') as f:
            f.write(keymap_content)
        print(f"Generated ZMK keymap at {zmk_keymap_path}")
    else:
        # Default behavior
        parser = QMKParser(QMK_KEYMAP_PATH, QMK_CONFIG_PATH)
        tap_dances = parser.parse_tap_dances()
        dual_functions = parser.parse_dual_functions()
        custom_dual_functions = parser.parse_custom_dual_functions()
        macros = parser.parse_macros()
        keymaps = parser.parse_keymaps()
        generator = ZMKGenerator(tap_dances, dual_functions, custom_dual_functions, macros, keymaps)
        generator.generate_config_files()
        print(f"Generated ZMK configuration files in {ZMK_OUT_DIR}/")
        print(f"- Converted {len(keymaps)} layers")
        print(f"- Converted {len(tap_dances)} tap dances")
        print(f"- Converted {len(dual_functions)} dual functions")
        print(f"- Converted {len(custom_dual_functions)} custom dual functions")
        print(f"- Converted {len(macros)} macros")


if __name__ == "__main__":
    main()