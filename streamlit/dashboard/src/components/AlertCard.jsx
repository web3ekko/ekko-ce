import React from 'react';
import { Flex, Text, Badge } from '@tremor/react';

const getPriorityColor = (priority) => {
  switch (priority) {
    case 'High':
      return 'rose';
    case 'Medium':
      return 'amber';
    case 'Low':
      return 'blue';
    default:
      return 'gray';
  }
};

const getStatusColor = (status) => {
  switch (status) {
    case 'warning':
      return 'amber';
    case 'error':
      return 'rose';
    case 'success':
      return 'emerald';
    default:
      return 'blue';
  }
};

const AlertCard = ({ alert }) => {
  return (
    <div className={`p-4 rounded-lg border-l-4 border-${getStatusColor(alert.status)}-500 bg-${getStatusColor(alert.status)}-50`}>
      <Flex alignItems="start" justifyContent="between">
        <div>
          <Text className="font-medium">{alert.type}</Text>
          <Text className="text-gray-500 mt-1">{alert.message}</Text>
        </div>
        <div className="text-right">
          <Badge color={getPriorityColor(alert.priority)}>
            {alert.priority}
          </Badge>
          <Text className="text-gray-500 text-xs mt-2">{alert.time}</Text>
        </div>
      </Flex>
    </div>
  );
};

export default AlertCard;
