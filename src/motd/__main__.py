#!/usr/bin/env python3
import datetime
import json
import os, os.path
import random
import re
import shlex, subprocess
import textwrap

# Marks if the termux API can be used.
# None: auto-detect and auto-start API
# True: assume it is running
# False: disable usage of API
TERMUX_API = None

try:
  COL, ROW = os.get_terminal_size()
except OSError:
  # May have run from remote command like `git fetch`
  exit()

# Change from home directory to this directory
os.chdir(os.path.dirname(__file__))

# MOTD sections
WELCOME = """\
Welcome to Termux!
Starting on a {current_day}\
"""

PKG = """\
Working with packages:

 * Search packages:   pkg search <query>
 * Install a package: pkg install <package>
 * Upgrade packages:  pkg upgrade\
"""

REPO = """\
Subscribing to additional repositories:

 * Root:     pkg install root-repo
 * X11:      pkg install x11-repo\
"""

STATS = '{stats}'

QUOTE = """\
Quote of the day:

{quote}\
"""

# Specify which sections to display
SECTIONS = [
  WELCOME,
  PKG,
  REPO,
  STATS,
  QUOTE,
]

# Constants for use in placeholders
DT = datetime.datetime.now().astimezone()


# Helper functions
def part_of_day():
  h = DT.hour
  if 5 <= h < 12:
    return 'morning'
  elif 12 <= h < 18:
    return 'afternoon'
  elif 18 <= h < 21:
    return 'evening'
  return 'night'


def termux(cmd, timeout=3):
  """Execute the given termux command.

  This will automatically start the termux API
  when a command *first* times out.
  Commands may not work if the termux API is
  somehow stopped afterwards.

  :param cmd:
    The command to execute without
    the 'termux-' prefix.
  :param timeout:
    The amount of time in seconds to wait before
    terminating the command and raising
    TimeoutExpired. If None, no timeout is used.
  :returns:
    The decoded output as a string, or as a
    JSON object if it can be parsed.
  :raises SubprocessError:
    Either the command failed, timed out,
    or the termux API could not be started.

  """
  global TERMUX_API

  exc_unavailable = subprocess.SubprocessError(
    'Termux API is unavailable'
  )

  if TERMUX_API is False:
    raise exc_unavailable

  args = shlex.split('termux-' + cmd)

  # Execute command in subprocess
  try:
    p = subprocess.run(args, capture_output=True, timeout=timeout)
  except (subprocess.TimeoutExpired, OSError):
    if TERMUX_API is not None:
      raise

    # API may have crashed last session;
    # attempt to start it then re-run commamd
    print('Hang on, the Termux API is currently '
          'unavailable. Attempting to start it...')
    try:
      TERMUX_API = True
      termux('api-start')
    except (subprocess.TimeoutExpired, OSError):
      print('Termux API could not be accessed. '
            'Hiding Termux-related information...')
      raise exc_unavailable from None
    finally:
      # if any other exception happens,
      # we also want to disable the API
      TERMUX_API = False

    TERMUX_API = True
    return termux(cmd, timeout)

  # command worked, skip API start in the future
  TERMUX_API = True

  # Parse as JSON if possible
  try:
    return json.loads(p.stdout)
  except json.JSONDecodeError:
    return p.stdout.decode()


def wrap(text, indent=-1):
  """Wraps a string or a list of lines to fit
  the terminal's width.

  :param text:
    The text to wrap. If a string is given,
    wrapping is performed on each line.
    Otherwise for a sequence of strings, wrapping
    is performed on each string, assuming that
    they are already single-line strings.
  :param indent:
    The number of spaces to use for indenting
    the text. If set to -1, the leading whitespace
    on each line is used as the indentation.
  :returns: A string with each line wrapped.

  """
  if isinstance(text, str):
    text = text.splitlines()

  wrapper = textwrap.TextWrapper(
    width=COL,
    drop_whitespace=False,
    replace_whitespace=False,
    initial_indent=' ' * indent,
    subsequent_indent=' ' * indent
  )

  for i, line in enumerate(text):
    if indent == -1:
      leading = re.match(r'\s*', line).group()
      # wrapper.initial_indent = leading
      wrapper.subsequent_indent = leading

    text[i] = wrapper.fill(line)

  return '\n'.join(text)


# Placeholder functions
def get_current_day():
  return DT.strftime(f'%A {part_of_day()}').lower()


def get_quote():
  with open('jokes.txt') as f:
    lines = f.readlines()

  # To keep the same quote every day,
  # the current date is used to decide which
  # line to use, and also to shuffle the list
  # after the quotes are exhausted.
  #
  # This adds the chance of a quote repeating
  # consecutively, but it's a worthwhile tradeoff
  epoch = datetime.date.fromtimestamp(0)
  days = (DT.date() - epoch).days

  seed, i = divmod(days, len(lines))
  rand = random.Random(seed)

  rand.shuffle(lines)
  line = lines[i]

  return wrap(line.rstrip(), indent=4)


def get_stats():
  try:
    batt = termux('battery-status')
  except subprocess.SubprocessError:
    return ''

  temp = round(batt['temperature'], 1)

  lines = [
    f'Battery temperature: {temp}°C',
  ]

  return '\n'.join(lines)


v = {
  'current_day': get_current_day(),
  'quote': get_quote(),
  'stats': get_stats(),
}

# Format and remove empty sections before printing
for i, s in enumerate(SECTIONS):
  SECTIONS[i] = s.format(**v)

SECTIONS = map(wrap, filter(None, SECTIONS))

message = '\n\n'.join(SECTIONS)
print(message, end='\n\n')
