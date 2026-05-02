import argparse

from tigen.config import RunConfiguration
from zero import create_app


def main():
    parser = argparse.ArgumentParser(description="Run the Zero simulation")
    parser.add_argument("-t", "--ticks", type=int, help="Limit simulation to specified number of iterations")
    parser.add_argument("-r", "--release", action="store_true", help="Run in release mode (disable memory tracking)")
    parser.add_argument("-d", "--debug", type=int, help="Debug a specific entity by ID")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without TUI dashboard (headless mode)"
    )
    parser.add_argument(
        "--refresh-rate",
        type=float,
        default=10.0,
        help="TUI refresh rate in FPS (default: 10)"
    )

    args = parser.parse_args()

    config = RunConfiguration(debug_entity_id=args.debug)

    if args.headless:
        app = create_app(config)
    else:
        import logging
        logging.getLogger("zero").setLevel(logging.CRITICAL)

        from zero.tui import ZERO_DASHBOARD
        app = create_app(
            config,
            render_systems=[ZERO_DASHBOARD.create_render_system()],
            refresh_rate=args.refresh_rate,
            measurements=True,
        )

    app.run(max_ticks=args.ticks, debug_mode=not args.release)


if __name__ == "__main__":
    main()
