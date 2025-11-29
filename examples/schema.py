"""Example Python schema file for FRC scouting data encoding."""

from src.encoder.data_packer import ColumnSchema

SCHEMA = [
    ColumnSchema(
        name="ScoutName", kind="enum", bits=2, values=["Jude", "Dillon", "", ""]
    ),
    ColumnSchema(name="MatchNumber", kind="int", bits=8, int_max=200),
    ColumnSchema(name="TeamNumber", kind="int", bits=14, int_max=16383),
    ColumnSchema(name="Mobility", kind="int", bits=1, int_max=1),
    ColumnSchema(name="AutonL1Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL1Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL2Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL2Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL3Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL3Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL4Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonL4Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="AutonBargeAttempted", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonBargeScored", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonProcessorAttempted", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonProcessorScored", kind="int", bits=0, int_max=0),
    ColumnSchema(name="AutonAlgaeRemoved", kind="int", bits=0, int_max=0),
    ColumnSchema(name="TeleopL1Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL1Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL2Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL2Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL3Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL3Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL4Attempted", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopL4Scored", kind="int", bits=4, int_max=12),
    ColumnSchema(name="TeleopBargeAttempted", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopBargeScored", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopProcessorAttempted", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopProcessorScored", kind="int", bits=3, int_max=7),
    ColumnSchema(name="TeleopAlgaeRemoved", kind="int", bits=3, int_max=7),
    ColumnSchema(name="ClimbSuccessful", kind="int", bits=1, int_max=1),
    ColumnSchema(
        name="Climb", kind="enum", bits=2, values=["None", "Shallow", "Deep", "Park"]
    ),
    ColumnSchema(name="Breakdown", kind="enum", bits=1, values=["False", "True"]),
    ColumnSchema(name="DefenseDescription", kind="enum", bits=0, values=[""]),
    ColumnSchema(name="Notes", kind="enum", bits=1, values=["", "Some note"]),
]

