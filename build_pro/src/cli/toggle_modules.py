# toggle_modules.py – Command‑line tool to enable/disable CrownStar math modules
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core

def print_help():
    print("CrownStar Module Toggle Manager")
    print("Usage: python toggle_modules.py <module_name> [on|off]")
    print("       python toggle_modules.py list")
    print("Modules:")
    print(" base_3layer_jacobian, hessian_backprop, universal_approx,")
    print(" gurney_3stage, yegnanarayana_tensor, haykin_recursive,")
    print(" bishop_probabilistic, zurada_indexed, ultra_super_model")

def main():
    if len(sys.argv) < 2:
        print_help()
        return
    core = create_core()
    if sys.argv[1] == "list":
        active = core.modules.get_active()
        print("Currently active modules:")
        for m in active:
            print(f" + {m}")
        print("\nAll modules and their states:")
        for k, v in core.modules.modules_state.items():
            print(f" {k}: {'ON' if v else 'OFF'}")
    elif len(sys.argv) == 3:
        module = sys.argv[1]
        state = sys.argv[2].lower() == "on"
        try:
            core.set_module(module, state)
            config_path = "config/crownstar_config.json"
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            cfg["module_toggles"][module] = state
            with open(config_path, 'w') as f:
                json.dump(cfg, f, indent=2)
            print(f"Module {module} set to {'ON' if state else 'OFF'}")
        except ValueError as e:
            print(f"Error: {e}")
    else:
        print_help()

if __name__ == "__main__":
    main()
