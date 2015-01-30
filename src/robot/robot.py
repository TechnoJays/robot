"""This module contains the FRC robot class."""

# Imports

# If wpilib not available use pyfrc
try:
    import wpilib
except ImportError:
    from pyfrc import wpilib

import common
import drivetrain
import logging
import math
import parameters
import sys
import userinterface


class MyRobot(wpilib.SimpleRobot):
    """Controls the robot.

    This is the main robot class that controls the robot during all 3 modes.
    There is 1 method for each mode: Disabled, Autonomous, and OperatorControl
    (teleop).  The methods are called once from the main control loop each time
    the robot enters the states.

    """
    # Public member variables

    # Private member objects
    _drive_train = None
    _log = None
    _logger = None
    _parameters = None
    _user_interface = None

    # Private parameters

    # Private member variables
    _log_enabled = False
    _parameters_file = None
    _driver_alternate = False
    _driver_controls_swap_ratio = 1.0

    def _initialize(self, params, logging_enabled):
        """Initialize the robot.

        Initialize instance variables to defaults, read parameter values from
        the specified file, instantiate required objects and update status
        variables.

        Args:
            params: The parameters filename to use for configuration.
            logging_enabled: True if logging should be enabled.

        """
        self._logger = logging.getLogger(__name__)
        handler = None
        formatter = logging.Formatter('%(asctime)s - %(levelname)s:'
                                      '%(name)s:%(message)s')
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

        # Initialize public member variables

        # Initialize private member objects
        self._drive_train = None
        self._log = None
        self._parameters = None
        self._user_interface = None

        # Initialize private parameters

        # Initialize private member variables
        self._log_enabled = False
        self._parameters_file = None
        self._driver_alternate = False
        self._driver_controls_swap_ratio = 1.0

        # Read parameters file
        self._parameters_file = params
        self.load_parameters()

        # Create robot objects
        self._drive_train = drivetrain.DriveTrain("/py/par/drivetrain.par",
                                                  self._log_enabled)
        self._user_interface = userinterface.UserInterface(
                                                    "/py/par/userinterface.par",
                                                    self._log_enabled)

    def load_parameters(self):
        """Load values from a parameter file and create and initialize objects.

        Read parameter values from the specified file, instantiate required
        objects, and update status variables.

        Returns:
            True if the parameter file was processed successfully.

        """
        # Close and delete old objects
        self._parameters = None

        # Read the parameters file
        self._parameters = parameters.Parameters(self._parameters_file)
        section = __name__.lower()

        # Read parameters from the file
        if self._parameters:
            pass

        return True

    def RobotInit(self):
        """Performs robot-wide initialization.

        Called each time the robot enters the Disabled mode.

        """
        self._initialize("/py/par/robot.par", True)

    def _disabled_init(self):
        """Prepares the robot for Disabled mode."""
        self._set_robot_state(common.ProgramState.DISABLED)

        # Read sensors
        self._read_sensors()

        self.GetWatchdog().SetEnabled(False)

    def Disabled(self):
        """Control the robot during Disabled mode.

        Monitors the user input for a restart request.  This is
        useful during development to load new Python code and
        avoid rebooting the robot.

        """
        self._disabled_init()

        # Repeat this loop as long as we're in Disabled
        while self.IsDisabled():
            # Set all motors to be stopped (prevent motor safety errors)
            if self._drive_train:
                self._drive_train.drive(0.0, 0.0, False)

            # Read sensors
            self._read_sensors()

            wpilib.Wait(0.01)

    def _autonomous_init(self):
        """Prepares the robot for Autonomous mode."""
        # Perform initialization before looping

        # Read sensors
        self._read_sensors()

        self._set_robot_state(common.ProgramState.AUTONOMOUS)
        self.GetWatchdog().SetEnabled(False)

    def Autonomous(self):
        """Controls the robot during Autonomous mode.

        Instantiate a Class using default values.

        """
        # Autonomous initialization
        self._autonomous_init()

        # Repeat this loop as long as we're in Autonomous
        while self.IsAutonomous() and self.IsEnabled():

            # Read sensors
            self._read_sensors()

            wpilib.Wait(0.01)

    def _operator_control_init(self):
        """Prepares the robot for Teleop mode."""
        # Perform initialization before looping

        self._set_robot_state(common.ProgramState.TELEOP)

        # Enable the watchdog
        dog = self.GetWatchdog()
        dog.SetEnabled(True)
        dog.SetExpiration(1.0)

    def OperatorControl(self):
        """Controls the robot during Teleop/OperatorControl mode.

        Instantiate a Class using default values.

        """
        self._operator_control_init()
        dog = self.GetWatchdog()
        # Repeat this loop as long as we're in Teleop
        while self.IsOperatorControl() and self.IsEnabled():
            # Feed the watchdog timer
            dog.Feed()

            # Read sensors
            self._read_sensors()

            # Perform user controlled actions
            if self._user_interface:
                # Check for alternate speed mode request
                self._check_alternate_speed_modes()

                # Check swap drivetrain direction request
                self._check_swap_drivetrain_request()

                # Manually control the robot
                self._control_drive_train()

                # Update/store the UI button state
                self._user_interface.store_button_states(
                        userinterface.UserControllers.DRIVER)
                self._user_interface.store_button_states(
                        userinterface.UserControllers.SCORING)

            wpilib.Wait(0.01)

    def _read_sensors(self):
        """Have the objects read their sensors."""
        if self._drive_train:
            self._drive_train.read_sensors()

    def _set_robot_state(self, state):
        """Notify objects of the current mode."""
        if self._drive_train:
            self._drive_train.set_robot_state(state)
        if self._user_interface:
            self._user_interface.set_robot_state(state)

    def _check_alternate_speed_modes(self):
        """Check for alternate speed mode."""
        if (self._user_interface.get_button_state(
                        userinterface.UserControllers.DRIVER,
                        userinterface.JoystickButtons.LEFTBUMPER) == 1):
            self._driver_alternate = True
        else:
            self._driver_alternate = False

    def _check_swap_drivetrain_request(self):
        """Check if the driver wants to swap forward and reverse."""
        if (self._user_interface.get_button_state(
                        userinterface.UserControllers.DRIVER,
                        userinterface.JoystickButtons.RIGHTTRIGGER) == 1 and
            self._user_interface.button_state_changed(
                        userinterface.UserControllers.DRIVER,
                        userinterface.JoystickButtons.RIGHTTRIGGER)):
            # Swap the driver controls to be the opposite of what they were
            self._driver_controls_swap_ratio = (self._driver_controls_swap_ratio
                                                * -1.0)

    def _control_drive_train(self):
        """Manually control the drive train."""
        driver_left_y = self._user_interface.get_axis_value(
                userinterface.UserControllers.DRIVER,
                userinterface.JoystickAxis.LEFTY)
        driver_right_x = self._user_interface.get_axis_value(
                userinterface.UserControllers.DRIVER,
                userinterface.JoystickAxis.RIGHTX)
        if driver_left_y != 0.0 or driver_right_x != 0.0:
            if self._drive_train:
                driver_left_y = driver_left_y * self._driver_controls_swap_ratio
                self._drive_train.arcade_drive(driver_left_y, driver_right_x,
                                               False)
        else:
            self._drive_train.arcade_drive(0.0, 0.0, False)


def run():
    """Create the robot and start it."""
    robot = MyRobot()
    robot.StartCompetition()
