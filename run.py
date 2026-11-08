"""Offline source replay and exact scalar diagnostics."""
import argparse
import json
from pathlib import Path
from release_queries import reproduce as point, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['check-inputs', 'reproduce', 'audit']:
        sub = commands.add_parser(name)
        sub.add_argument('--inputs', type=Path, required=True)
        if name != 'check-inputs':
            sub.add_argument('--output', type=Path, required=True)
    unpack = commands.add_parser('unpack-inputs')
    unpack.add_argument('--archive', type=Path, required=True)
    unpack.add_argument('--output', type=Path, required=True)
    figure = commands.add_parser('figures')
    figure.add_argument('--inputs', type=Path, required=True)
    figure.add_argument('--run', type=Path, required=True)
    figure.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'unpack-inputs':
            result = point.unpack_inputs(args.archive, args.output)
        elif args.command == 'check-inputs':
            result = {'verified_input_files': len(point.verify_inputs(args.inputs))}
        elif args.command == 'figures':
            from release_queries import figures
            result = figures.run(args.inputs, args.run, args.output)
        elif args.command == 'audit':
            result = audit.run(args.inputs, args.output)
        else:
            result = point.reproduce(args.inputs, args.output)
            fits = point.read_json(args.output/'fits.json')
            result['audits'] = audit.run(args.inputs, args.output/'audits', fits=fits)
            (args.output/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    main()
