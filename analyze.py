from datetime import datetime
import re
import sys

file_name = "log_snippet.txt"
#file_name = "eqlog_Vill_P1999Green.txt"
# TODO - need a way to tell it which chain to analyze when 
#   there are many. Probably default to most recent
#   Add feature to specify a date to start after
#   Also maybe a date range, so a start and end date
# TODO - Summary doesn't understand skips
#   doesn't understand subsequent cleric firing correct for late heal
#   doesn't understand tank switching
#   When wrong target is healed, subsequent cleric gets switched target also
#   Doesn't know if you ranged a heal or ducked or went oom
#   If you double tap because you went early, it penalizes
#file_name = "tuna_snippet_2025_01_12.txt"
#file_name = "vindi_heals_2025_01_15.txt"

string_format = "%a %b %d %H:%M:%S %Y"

class ch():
    """Contains the detail of a Complete Heal
    date - the log timestamp of the shout
    cleric - the cleric shouting
    number - the number the cleric used in their macro
    target - who is the cleric targeting
    expected_delay - the expected chain delay, based on the guild message:
      Character tells the guild, '!chainspeed #'
      Where the # is the delay in seconds.
    """
    def __init__(self, date, cleric, number, target, expected_delay):
        self.date = date
        self.cleric = cleric
        self.number = number
        self.target = target
        self.expected_delay = expected_delay
    def __str__(self):
        output = " ".join([str(self.date), self.cleric, self.number, self.target])
        return output

class comparison():
    """Capture the results of comparing 2 subsequent complete heals
    ordered - Boolean that is True if the chain is in order
      TODO - It's always True for 001 cleric, even if they fire in 
      the middle of the chain
    delay - Duration in seconds since the previous complete heal
    target - This will be set by the compare_sequential function
      Expected values: "Same" or "New Target"
      Same means the previous CH was targeted at the same toon
      New Target would imply the target has changed.
    """
    def __init__(self, ordered, delay, target):
        self.ordered = ordered
        self.delay = delay
        self.target = target
    def __str__(self):
        output = " ".join([" In order:", str(self.ordered), "\n", "Delay:", str(self.delay), "\n","Target:", str(self.target)])
        return output

class cleric():
    """
    """
    def __init__(self, name):
        self.name = name
        self.heals = 0
        self.switched_targets = 0
        self.out_of_order = 0
        self.delay_diffs = []
        self.grade = 100
    def __str__(self):
        self.do_grading()
        output = "Name: " + self.name + "\n"
        output += "Total Heals: " + str(self.heals) + "\n"
        output += "Switched Targets: " + str(self.switched_targets) + "\n"
        output += "Out of Order: " + str(self.out_of_order) + "\n"
        output += "Delay Diffs: " + str(self.delay_diffs) + "\n" 
        output += "Grade: " + format(self.grade, ".2f") + "\n"

        return output
    def do_heal(self, switched=False, ordered=True, delay_diff=0):
        self.heals += 1
        if switched:
            self.switched_targets += 1
        if not ordered:
            self.out_of_order += 1
        if delay_diff != 0:
            self.delay_diffs.append(delay_diff)
    def do_grading(self):
        demerits = 0
        for diff in self.delay_diffs:
            if diff > 1 or diff < -1:
                demerits += 1
            if diff == 1 or diff == -1:
                demerits += 0.2
        demerits += self.switched_targets
        demerits += self.out_of_order
        self.grade = (self.heals - demerits) / self.heals * 100



def extract_date(line):
    """Get an everquest log date and turn it into a python date"""
    stripped = line.split("[")
    date = stripped[1].split("]")
    x = datetime.strptime(date[0], string_format)
    return x

def extract_cleric(line):
    """Get the cleric name from a chain heal log line"""
    stripped = line.split("] ")
    player = stripped[1].split(" shouts")
    return player[0]

def extract_number(line):
    """Get the chain number from a chain heal log line"""
    stripped = line.split("GG ")
    number = stripped[1].split(" CH --")
    return number[0]

def extract_target(line):
    """Get the target from a chain heal log line"""
    stripped = line.split(" -- ")
    target = stripped[1].split("'")
    return target[0].strip()

def is_chain_line(line):
    """Match a complete heal log line"""
    pattern = r"shouts, 'GG ... CH -- "
    if re.search(pattern, line):
        return True

def compare_sequential(current: ch, previous: ch):
    """Compare a complete heal to the previous complete and return a comparison."""
    in_order = False
    target = "New Target"
    timedelta = current.date - previous.date
    delay = timedelta.days * 24 * 3600 + timedelta.seconds
    if current.number != "001":
        try: 
            if int(current.number) - 1 == int(previous.number):
                in_order = True
        except ValueError:
            pass
    else:
        in_order = True
    if current.target == previous.target:
        target = "Same"
    return comparison(in_order, delay, target)

def start_checking(line):
    """Find a startchain message and start checking for complete heals"""
    pattern = r" guild, '!startchain"
    if re.search(pattern, line):
        print(line)
        return True
    
def stop_checking(line):
    """Find a stopchain message and stop checking for complete heals"""
    pattern = r" guild, '!stopchain"
    if re.search(pattern, line):
        print(line)
        return True
    
def chain_speed(line, expected_delay):
    """Find a message setting the chain speed, and set it"""
    pattern = r" guild, '!chainspeed (\d)"
    matches = re.findall(r" guild, '!chainspeed (\d)", line)
    if re.search(pattern, line):
        print(line)
        print("Setting Expected Delay to " + matches[0])
        return matches[0]
    return expected_delay

def validate(diff, current, previous):
    """If any of these things are off, output that info"""
    if not diff.ordered:
        print("** Out of Order")
    if int(diff.delay) != int(previous.expected_delay):
        print("** Delay was " + str(diff.delay) + " expected " + str(previous.expected_delay))
    if diff.target != "Same":
        print("** Target switch, was " + previous.target + " new target: " + current.target)

# Parse the logfile
def parse():
    # Start with checking set to False
    checking = False
    # A list of complete heals to populate
    chain = []
    # default the expected delay to 1
    expected_delay = 1
    with open(file_name) as logfile:
        for line in logfile:
            if start_checking(line):
                checking = True
            if stop_checking(line):
                checking = False
            if checking:
                expected_delay = chain_speed(line, expected_delay)
            if is_chain_line(line) and checking:
                date = extract_date(line)
                cleric = extract_cleric(line)
                number = extract_number(line)
                target = extract_target(line)
                chain.append(ch(date, cleric, number, target, expected_delay))
    return chain

def insert_cleric(diff, heal, clerics):
    clerics.append(cleric(heal.cleric))

def add_heal(diff, heal, clerics):
    updated = False
    for index, cleric in enumerate(clerics):
        if heal.cleric == cleric.name:
            switched = False
            if diff.target != "Same":
                switched = True
            delay = diff.delay - int(heal.expected_delay)
            clerics[index].do_heal(switched, diff.ordered, delay)
            updated = True
    if not updated:
        insert_cleric(diff, heal, clerics)
        switched = False
        if diff.target != "Same":
            switched = True
        delay = diff.delay - int(heal.expected_delay)
        clerics[-1].do_heal(switched, diff.ordered, delay)



# Output the analyzation
def analyze(chain, clerics):
    previous = None  # Initialize the previous value
    for heal in chain:
        if previous is not None:
            print("CH:", heal)
            diff = compare_sequential(heal, previous)
            validate(diff, heal, previous)
            add_heal(diff, heal, clerics)
        previous = heal
    for cleric in clerics:
        print(cleric)

def main():
    clerics = []
    chain = parse()
    analyze(chain, clerics)

if __name__ == "__main__":
    main()
