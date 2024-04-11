#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from ariac_msgs.msg import (
    Order as OrderMsg,
    AGVStatus as AGVStatusMsg,
    AssemblyTask as AssemblyTaskMsg,
    Part as PartMsg,
    AdvancedLogicalCameraImage as AdvancedLogicalCameraImageMsg,
    PartPose as PartPoseMsg
)
from utils import(
    Order,
    KittingTask,
    KittingPart,
    Mult_pose,
    Quart_to_RPY,
    RAD_TO_DEGREE,
    AdvancedLogicalCameraImage
    
)

class ReadStoreOrders():
    '''
    Class for subscribing to order messages and storing them in a queue.

    Args:
        node (rclpy.node.Node): The ROS node.
        topic_name (str): Name of the topic where orders are published.
        order_queue (collections.deque): Queue to store orders.
        callback_group: Callback group for this class.
    '''

    _AGV_destinations = {
        AGVStatusMsg.KITTING: 'kitting station',
        AGVStatusMsg.ASSEMBLY_FRONT: 'front assembly station',
        AGVStatusMsg.ASSEMBLY_BACK: 'back assembly station',
        AGVStatusMsg.WAREHOUSE: 'warehouse',
    }
    '''Dictionary for converting AGVDestination constants to strings'''

    _Assembly_stations = {
        AssemblyTaskMsg.AS1: 'assembly station 1',
        AssemblyTaskMsg.AS2: 'assembly station 2',
        AssemblyTaskMsg.AS3: 'assembly station 3',
        AssemblyTaskMsg.AS4: 'assembly station 4',
    }

    _color_of_parts = {
        PartMsg.RED: 'red',
        PartMsg.BLUE: 'blue',
        PartMsg.GREEN: 'green',
        PartMsg.ORANGE: 'orange',
        PartMsg.PURPLE: 'purple',
    }
    '''Dictionary for converting Part color constants to strings'''

    _part_color_symbol = {
        PartMsg.RED: '🟥',
        PartMsg.BLUE: '🟦',
        PartMsg.GREEN: '🟩',
        PartMsg.ORANGE: '🟧',
        PartMsg.PURPLE: '🟪',
    }

    _type_of_parts = {
        PartMsg.BATTERY: 'battery',
        PartMsg.PUMP: 'pump',
        PartMsg.REGULATOR: 'regulator',
        PartMsg.SENSOR: 'sensor',
    }
    '''Dictionary for converting Part type constants to strings'''

    def __init__(self, node, topic_name1,topic_name2, order_queue, callback_group):
        '''
        Initialize ReadStoreOrders.

        Args:
            node (rclpy.node.Node): The ROS node.
            topic_name (str): Name of the topic where orders are published.
            order_queue (collections.deque): Queue to store orders.
            callback_group: Callback group for this class.
        '''
        sim_time = Parameter(
            "use_sim_time",
            rclpy.Parameter.Type.BOOL,
            True
        )
        self.node = node
        self.order_topic1 = topic_name1
        self.order_topic2 = topic_name2
        self._orders = order_queue
        self.orders_subcriber = node.create_subscription(OrderMsg, self.order_topic1, self._orders_callback, 10, callback_group=callback_group)
        self._parsing_Flag = True
        node.set_parameters([sim_time])
        # Subscriber to the logical camera topic
        self._advanced_camera0_sub = node.create_subscription(
            AdvancedLogicalCameraImageMsg,
            self.order_topic2,
            self._advanced_camera0_cb,
            qos_profile_sensor_data)

        # Store each camera image as an AdvancedLogicalCameraImage object
        self._camera_image: AdvancedLogicalCameraImage = None
        
    @property
    def camera_image(self):
        return self._camera_image    
    def _advanced_camera0_cb(self, msg: AdvancedLogicalCameraImageMsg):
        '''Callback for the topic /ariac/sensors/advanced_camera_0/image

        Arguments:
            msg -- AdvancedLogicalCameraImage message
        '''
        self._camera_image = AdvancedLogicalCameraImage(msg.part_poses,
                                                        msg.tray_poses,
                                                        msg.sensor_pose)

    @property
    def orders(self):
        '''
        Property to access the orders queue.

        Returns:
            collections.deque: The queue containing orders.
        '''
        return self._orders

    @property
    def _the_order_to_parse(self):
        '''
        Property to get the parsing flag.

        Returns:
            bool: The parsing flag indicating if the order should be parsed.
        '''
        return self._parsing_Flag
    
    @_the_order_to_parse.setter
    def _the_order_to_parse(self, value=True):
        '''
        Setter for the parsing flag.

        Args:
            value (bool): The value to set for the parsing flag.
        '''
        self._parsing_Flag = value
        
    def _orders_callback(self, msg: Order):
        '''
        Callback function for order messages.

        Args:
            msg (Order): The received order message.
        '''
        order = Order(msg)

        if order.order_priority:
            self._orders.appendleft(order)
        else:
            self._orders.append(order)

        if self._parsing_Flag:
            self.node.get_logger().info(self._parse_the_order(order))
    
    def parse_advanced_camera_image(self, image: AdvancedLogicalCameraImage) -> str:
        '''
        Parse an AdvancedLogicalCameraImage message and return a string representation.
        '''

        if len(image._part_poses) == 0:
            return 'No parts detected'

        output = '\n\n'
        for i, part_pose in enumerate(image._part_poses):
            part_pose: PartPoseMsg
            output += '==========================\n'
            _color_of_parts = ReadStoreOrders._color_of_parts[part_pose.part.color].capitalize()
            _part_color_symbol = ReadStoreOrders._part_color_symbol[part_pose.part.color]
            _type_of_parts = ReadStoreOrders._type_of_parts[part_pose.part.type].capitalize()
            output += f'Part {i+1}: {_part_color_symbol} {_color_of_parts} {_type_of_parts}\n'
            output += '--------------------------\n'
            output += 'Camera Frame\n'
            output += '--------------------------\n'

            output += '  Position:\n'
            output += f'    x: {part_pose.pose.position.x:.3f} (m)\n'
            output += f'    y: {part_pose.pose.position.y:.3f} (m)\n'
            output += f'    z: {part_pose.pose.position.z:.3f} (m)\n'

            roll, pitch, yaw = Quart_to_RPY(part_pose.pose.orientation)
            output += '  Orientation:\n'
            output += f'    roll: {RAD_TO_DEGREE(roll)}\n'
            output += f'    pitch: {RAD_TO_DEGREE(pitch)}\n'
            output += f'    yaw: {RAD_TO_DEGREE(yaw)}\n'

            part_world_pose = Mult_pose(image._sensor_pose, part_pose.pose)
            output += '--------------------------\n'
            output += 'World Frame\n'
            output += '--------------------------\n'

            output += '  Position:\n'
            output += f'    x: {part_world_pose.position.x:.3f} (m)\n'
            output += f'    y: {part_world_pose.position.y:.3f} (m)\n'
            output += f'    z: {part_world_pose.position.z:.3f} (m)\n'

            roll, pitch, yaw = Quart_to_RPY(part_world_pose.orientation)
            output += '  Orientation:\n'
            output += f'    roll: {RAD_TO_DEGREE(roll)}\n'
            output += f'    pitch: {RAD_TO_DEGREE(pitch)}\n'
            output += f'    yaw: {RAD_TO_DEGREE(yaw)}\n'

            output += '==========================\n\n'

        return output       
    def _parse_kitting_task(self, kitting_task: KittingTask):
        '''
        Parses a kitting task and returns a string representation.

        Args:
            kitting_task (KittingTask): The kitting task object.

        Returns:
            str: String representation of the kitting task.
        '''
        output = 'Type: Kitting\n'
        output += '==========================\n'
        output += f'AGV Number: {kitting_task.agv_number}\n'
        output += f'Destination: {ReadStoreOrders._AGV_destinations[kitting_task.destination]}\n'
        output += f'Tray ID: {kitting_task.tray_id}\n'
        output += 'Products:\n'
        output += '==========================\n'

        quadrants = {1: "Quadrant 1: -",
                     2: "Quadrant 2: -",
                     3: "Quadrant 3: -",
                     4: "Quadrant 4: -"}

        for i in range(1, 5):
            product: KittingPart
            for product in kitting_task.parts:
                if i == product.quadrant:
                    _color_of_parts = ReadStoreOrders._color_of_parts[product.part.color].capitalize()
                    _part_color_symbol = ReadStoreOrders._part_color_symbol[product.part.color]
                    _type_of_parts = ReadStoreOrders._type_of_parts[product.part.type].capitalize()
                    quadrants[i] = f'Quadrant {i}: {_part_color_symbol} {_color_of_parts} {_type_of_parts}'

        output += f'\t{quadrants[1]}\n'
        output += f'\t{quadrants[2]}\n'
        output += f'\t{quadrants[3]}\n'
        output += f'\t{quadrants[4]}\n'

        return output

    def _parse_the_order(self, order: Order):
        '''
        Parse an order message and return a string representation.

        Args:
            order (Order): The order message.

        Returns:
            str: String representation of the order message.
        '''
        output = '\n\n==========================\n'
        output += f'Order ID of Received Order: {order.order_id}\n'
        output += f'Priority of the Order : {order.order_priority}\n'

        if order.order_type == OrderMsg.KITTING:
            output += self._parse_kitting_task(order.order_task)
        else:
            output += 'Type: Unknown\n'

        return output

