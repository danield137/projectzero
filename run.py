import argparse

from zero import Simulation
from sim.config import RunConfiguration


def main():
    parser = argparse.ArgumentParser(description="Run the Zero simulation")
    parser.add_argument("-t", "--ticks", type=int, help="Limit simulation to specified number of iterations")
    parser.add_argument("-r", "--release", action="store_true", help="Run in release mode (disable memory tracking)")
    parser.add_argument("-d", "--debug", type=int, help="Debug a specific entity by ID")
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Use TUI dashboard mode instead of log output"
    )
    parser.add_argument(
        "--tui-interval",
        type=int,
        default=100,
        help="TUI update interval in ticks (default: 100)"
    )
    parser.add_argument(
        "--tui-delay",
        type=float,
        default=0.0,
        help="Delay in seconds between ticks (default: 0)"
    )

    args = parser.parse_args()

    config = RunConfiguration(debug_entity_id=args.debug)
    sim = Simulation(config)

    if args.tui:
        from zero.tui import run_with_tui
        run_with_tui(
            sim,
            max_ticks=args.ticks,
            debug_mode=not args.release,
            update_interval=args.tui_interval,
            delay=args.tui_delay
        )
    else:
        sim.run(max_ticks=args.ticks, debug_mode=not args.release)


if __name__ == "__main__":
    main()
