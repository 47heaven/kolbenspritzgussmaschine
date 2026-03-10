# Project Context

This repository contains the software for a student-built desktop injection molding machine.

The machine melts plastic in a heated crucible and injects it into molds.

The main task of the control software is to regulate the temperature of the crucible.

## Control Problem

The crucible must reach and maintain a temperature between approximately 200°C and 300°C.

Heating is done with cartridge heaters.

Temperature is measured using a thermocouple sensor.

The controller uses a PID algorithm to regulate heater power.

## Control Loop

Control loop structure:

Temperature Sensor
→ temperature measurement

PID Controller
→ compute heater power

Heater Driver
→ set heating power

Safety System
→ shutdown on fault

## Safety Requirements

The system must shut down heating if:

- sensor failure occurs
- temperature exceeds safety limit
- controller stops responding

## User Interface

The machine will be operated via a touchscreen GUI.

GUI should allow:

- display current temperature
- set target temperature
- start/stop heating
- display system status
- show error messages

## Development Notes

The control loop must run independently of the GUI.

The GUI should not directly control hardware.

Instead, the GUI communicates with the controller application.