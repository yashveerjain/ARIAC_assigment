import os
import yaml
from functools import partial

import rclpy
from rclpy.qos import qos_profile_sensor_data

from ariac_msgs.msg import (
    Order as OrderMsg,
    AGVStatus as AGVStatusMsg,
    AssemblyTask as AssemblyTaskMsg,
    Part as PartMsg,
    AdvancedLogicalCameraImage as AdvancedLogicalCameraImageMsg,
    BasicLogicalCameraImage as BasicLogicalCameraImageMsg,
    PartPose as PartPoseMsg
)
from sensor_msgs.msg import (
    Image as ImageMsg,
    PointCloud as PointCloudMsg,
    LaserScan as LaserScanMsg,
)
from read_store_orders import ReadStoreOrders
from utils import (  
    Mult_pose,
    Quart_to_RPY,
    AdvancedLogicalCameraImage
)
from launch_ros.substitutions import FindPackageShare
    

# Constants mapping ARIAC sensor types to their ROS message types
ARIAC_SENSORS_2_TYPE = {
    'rgb_camera': "rgb_image",
    'basic_logical_camera': "image",
    'advanced_logical_camera': "image",
}

# Constants mapping ARIAC sensor types to their ROS message classes
ARIAC_SENSORS_2_Msg = {
    'rgb_camera': ImageMsg,
    'basic_logical_camera': BasicLogicalCameraImageMsg,
    'advanced_logical_camera': AdvancedLogicalCameraImageMsg,
}

class SensorRead():
    def __init__(self, node, callback_group, sensor_config="sensors"):
        # Finding the package share directory
        pkg_share = FindPackageShare(package='rwa5_2').find('rwa5_2')
        sensor_config_path = os.path.join(pkg_share, 'config', sensor_config + ".yaml")
        
        # Initialize node and sensor data list
        self.node = node
        self.sensor_data = []

        # Load sensor configuration from YAML file
        with open(sensor_config_path, "r") as file:
            self.yaml_data = yaml.safe_load(file)
        
        # Initialize sensors_info dictionary
        self.sensors_info = {}
        
        # Create subscriptions for each sensor based on configuration
        for sensor_name, info in self.yaml_data["sensors"].items():
            self.sensors_info[sensor_name] = self.node.create_subscription(
                ARIAC_SENSORS_2_Msg[info["type"]],
                f"/ariac/sensors/{sensor_name}/{ARIAC_SENSORS_2_TYPE[info['type']]}",
                partial(self._advanced_camera_cb, name=sensor_name),
                qos_profile_sensor_data, callback_group=callback_group   
            )

        # Initialize sensor_data dictionary
        self.sensor_data = {}

    def _advanced_camera_cb(self, msg: AdvancedLogicalCameraImageMsg, name: str):
        '''
        Callback for the topic advanced_camera

        Arguments:
            msg -- AdvancedLogicalCameraImage message
            name -- Name of the sensor
        '''
        # Parse AdvancedLogicalCameraImage message
        _image = AdvancedLogicalCameraImage(msg.part_poses,
                                            msg.tray_poses,
                                            msg.sensor_pose)
        # Store parsed data in sensor_data dictionary
        self.sensor_data[name] = self.parse_advanced_camera_image(_image)
     
    def parse_advanced_camera_image(self, image: AdvancedLogicalCameraImage) -> str:
        '''
        Parse an AdvancedLogicalCameraImage message and return a string representation.
        '''

        # Initialize output list
        output = []
        
        # Process part poses
        for i, part_pose in enumerate(image._part_poses):
            part_world_pose = Mult_pose(image._sensor_pose, part_pose.pose)
            roll, pitch, yaw = Quart_to_RPY(part_world_pose.orientation)
            output.append({
                "is_part": True,
                "pose": [part_world_pose.position.x, part_world_pose.position.y, part_world_pose.position.z],
                "orientation": [roll, pitch, yaw],
                "color": part_pose.part.color,
                "type": part_pose.part.type,
                "tray_id": None
            })
        
        # Process tray poses
        for i, tray in enumerate(image._tray_poses):
            tray_world_pose = Mult_pose(image._sensor_pose, tray.pose)
            roll, pitch, yaw = Quart_to_RPY(tray_world_pose.orientation)
            output.append({
                "is_part": False,
                "pose": [tray_world_pose.position.x, tray_world_pose.position.y, tray_world_pose.position.z],
                "orientation": [roll, pitch, yaw],
                "color": None,
                "type": None,
                "tray_id": tray.id
            })

        # Return parsed output
        return output


        