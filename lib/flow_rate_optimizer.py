"""Helper to analyze and optimize district flow rates for larger delta T.

This module helps you understand current flow rates and systematically reduce them
to achieve larger temperature differences (delta T) across your 5G district system.

The relationship: Q = m_dot * cp * delta_T
- Q = heat transfer (W) [from building loads]
- m_dot = mass flow rate (kg/s)
- cp = specific heat of water (~4200 J/kg·K)
- delta_T = temperature difference (K)

Reducing m_dot increases delta_T for the same Q.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple


def load_sys_params(sys_param_path: Path) -> Dict[str, Any]:
    """Load system parameters from JSON file."""
    with open(sys_param_path, "r") as f:
        return json.load(f)


def save_sys_params(sys_param_path: Path, params: Dict[str, Any]) -> None:
    """Save system parameters to JSON file."""
    with open(sys_param_path, "w") as f:
        json.dump(params, f, indent=2)


def get_current_flow_rates(params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract current flow rate settings.

    Returns:
        dict with keys:
            - central_pump_flow_rate: current flow rate (kg/s) or None if autosized
            - central_pump_flow_rate_autosized: whether it's being auto-calculated
            - ets_pump_flow_rate: flow rate per building connection (kg/s)
    """
    fifth_gen = params.get("district_system", {}).get("fifth_generation", {})
    central_pump = fifth_gen.get("central_pump_parameters", {})

    # Get first building's ETS flow rate (they're all the same typically)
    buildings = params.get("buildings", [])
    ets_flow = None
    if buildings:
        fifth_gen_ets = buildings[0].get("fifth_gen_ets_parameters", {})
        ets_flow = fifth_gen_ets.get("ets_pump_flow_rate")

    return {
        "central_pump_flow_rate": central_pump.get("pump_flow_rate"),
        "central_pump_flow_rate_autosized": central_pump.get(
            "pump_flow_rate_autosized", False
        ),
        "ets_pump_flow_rate": ets_flow,
        "num_buildings": len(buildings),
    }


def analyze_flow_rates(sys_param_path: Path) -> None:
    """Analyze and display current flow rates."""
    params = load_sys_params(sys_param_path)
    rates = get_current_flow_rates(params)

    print("\n" + "=" * 70)
    print("CURRENT FLOW RATE CONFIGURATION")
    print("=" * 70)
    print(f"System Parameters File: {sys_param_path}")
    print(f"Number of Buildings: {rates['num_buildings']}")
    print("\nCentral District Pump:")
    print(f"  - Flow Rate: {rates['central_pump_flow_rate']} kg/s")
    print(f"  - Auto-sized: {rates['central_pump_flow_rate_autosized']}")
    print("\nPer-Building ETS Pump:")
    print(f"  - Flow Rate: {rates['ets_pump_flow_rate']} kg/s")
    print("\nNOTE: Auto-sizing means the pump_flow_rate value above is ignored")
    print("      and a value is calculated based on peak loads with delta_T=5C")
    print("=" * 70 + "\n")


def reduce_flow_rates(
    sys_param_path: Path,
    central_pump_reduction_factor: float = 1.0,
    ets_pump_reduction_factor: float = 1.0,
    disable_autosizing: bool = True,
    output_path: Path = None,
    backup: bool = True,
) -> Dict[str, Tuple[float, float]]:
    """Reduce flow rates to increase delta T.

    Args:
        sys_param_path: Path to system_params.json
        central_pump_reduction_factor: Multiply central pump flow by this (e.g., 0.8 = 20% reduction)
        ets_pump_reduction_factor: Multiply ETS pump flow by this (e.g., 0.8 = 20% reduction)
        disable_autosizing: Set pump_flow_rate_autosized=False so manual values are used
        output_path: Where to save modified params. If None, overwrites input.
        backup: Create a .backup file before modifying.

    Returns:
        dict with keys:
            - central_pump: (old_value, new_value) in kg/s
            - ets_pump: (old_value, new_value) in kg/s
    """
    if output_path is None:
        output_path = sys_param_path

    # Backup if requested
    if backup and output_path == sys_param_path:
        backup_path = sys_param_path.with_suffix(".json.backup")
        import shutil

        shutil.copy(sys_param_path, backup_path)
        print(f"Backup created: {backup_path}")

    params = load_sys_params(sys_param_path)
    old_rates = get_current_flow_rates(params)

    # Modify central pump
    fifth_gen = params["district_system"]["fifth_generation"]
    central_pump = fifth_gen["central_pump_parameters"]

    old_central = central_pump.get("pump_flow_rate", 0)
    if old_central > 0:
        new_central = old_central * central_pump_reduction_factor
        central_pump["pump_flow_rate"] = round(new_central, 6)

    if disable_autosizing:
        central_pump["pump_flow_rate_autosized"] = False

    # Modify ETS pump for all buildings
    for building in params.get("buildings", []):
        fifth_gen_ets = building.get("fifth_gen_ets_parameters", {})
        old_ets = fifth_gen_ets.get("ets_pump_flow_rate", 0)
        if old_ets > 0:
            new_ets = old_ets * ets_pump_reduction_factor
            fifth_gen_ets["ets_pump_flow_rate"] = round(new_ets, 6)

    save_sys_params(output_path, params)

    new_rates = get_current_flow_rates(params)

    print("\n" + "=" * 70)
    print("FLOW RATES UPDATED")
    print("=" * 70)
    print("Central Pump Flow Rate:")
    print(f"  OLD: {old_central:.6f} kg/s")
    print(f"  NEW: {new_rates['central_pump_flow_rate']:.6f} kg/s")
    print(f"  Change: {central_pump_reduction_factor:.1%}")

    print("\nETS Pump Flow Rate (per building):")
    print(f"  OLD: {old_rates['ets_pump_flow_rate']:.6f} kg/s")
    print(f"  NEW: {new_rates['ets_pump_flow_rate']:.6f} kg/s")
    print(f"  Change: {ets_pump_reduction_factor:.1%}")

    print(f"\nAuto-sizing disabled: {disable_autosizing}")
    print(f"Output saved to: {output_path}")
    print("=" * 70 + "\n")

    return {
        "central_pump": (old_central, new_rates["central_pump_flow_rate"]),
        "ets_pump": (old_rates["ets_pump_flow_rate"], new_rates["ets_pump_flow_rate"]),
    }


def estimate_delta_t_change(
    old_flow_rate: float,
    new_flow_rate: float,
    old_delta_t: float = 5.0,
) -> float:
    """Estimate new delta T based on flow rate reduction.

    Assumes constant heat load: Q = m_dot * cp * delta_T
    So: new_delta_T = old_delta_T * (old_flow / new_flow)

    Args:
        old_flow_rate: Original flow rate (kg/s)
        new_flow_rate: New flow rate (kg/s)
        old_delta_t: Original delta T assumption (K), default 5K for 5G

    Returns:
        Estimated new delta T (K)
    """
    if new_flow_rate <= 0:
        return 0
    return old_delta_t * (old_flow_rate / new_flow_rate)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print(
            "  python flow_rate_optimizer.py <sys_params_path> [analyze|reduce] [reduction_factor]"
        )
        print("\nExamples:")
        print("  # Analyze current rates:")
        print("  python flow_rate_optimizer.py sys_params.json analyze")
        print("\n  # Reduce by 20% (multiply by 0.8):")
        print("  python flow_rate_optimizer.py sys_params.json reduce 0.8")
        print("\n  # Reduce central pump by 25%, ETS by 15%:")
        print("  python flow_rate_optimizer.py sys_params.json reduce 0.75 0.85")
        sys.exit(1)

    sys_param_path = Path(sys.argv[1])

    if not sys_param_path.exists():
        print(f"Error: File not found: {sys_param_path}")
        sys.exit(1)

    command = sys.argv[2] if len(sys.argv) > 2 else "analyze"

    if command == "analyze":
        analyze_flow_rates(sys_param_path)
    elif command == "reduce":
        central_factor = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
        ets_factor = float(sys.argv[4]) if len(sys.argv) > 4 else central_factor

        # Estimate impact
        results = reduce_flow_rates(
            sys_param_path,
            central_pump_reduction_factor=central_factor,
            ets_pump_reduction_factor=ets_factor,
        )

        # Show estimated delta T increase
        print("ESTIMATED DELTA T IMPACT:")
        print("-" * 70)
        old_central, new_central = results["central_pump"]
        if old_central > 0:
            old_dt = 5.0  # Default 5G assumption
            new_dt = estimate_delta_t_change(old_central, new_central, old_dt)
            print(f"Central Loop (assuming initial {old_dt}K delta T):")
            print(f"  NEW estimated delta T: {new_dt:.1f}K")
            print(f"  Improvement: {new_dt - old_dt:+.1f}K")

        print("\nNEXT STEPS:")
        print("1. Review the modified system params file")
        print("2. Regenerate your 5G models with the new flow rates")
        print("3. Run simulations and check supply/return temperatures in results")
        print("4. Adjust further if needed (test incrementally)")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
