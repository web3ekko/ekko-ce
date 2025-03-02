import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Button,
  TextInput,
  Select,
  SelectItem,
  Grid,
  Col,
  MultiSelect,
  MultiSelectItem,
  Flex
} from '@tremor/react';
import useStore from '../store/store';
import AlertCard from '../components/AlertCard';

const Alerts = () => {
  const { alerts, addAlert } = useStore();
  const [showCreateAlert, setShowCreateAlert] = useState(false);
  const [alertType, setAlertType] = useState('Price Alert');
  const [alertCondition, setAlertCondition] = useState('');
  const [alertPriority, setAlertPriority] = useState('Medium');
  const [notificationChannels, setNotificationChannels] = useState([]);
  
  // Filters
  const [typeFilter, setTypeFilter] = useState('All Types');
  const [priorityFilter, setPriorityFilter] = useState('All Priorities');
  const [sortOrder, setSortOrder] = useState('Newest First');

  const alertTypes = [
    'Price Alert',
    'Workflow Alert',
    'Smart Contract Alert'
  ];

  const priorities = ['High', 'Medium', 'Low'];
  
  const notificationOptions = ['Email', 'Push', 'Discord'];

  const handleCreateAlert = () => {
    if (!alertCondition) return;

    const newAlert = {
      id: alerts.length + 1,
      type: alertType,
      message: alertCondition,
      time: new Date().toISOString().replace('T', ' ').substring(0, 19),
      status: alertPriority === 'High' ? 'warning' : 'info',
      priority: alertPriority
    };

    addAlert(newAlert);
    setAlertCondition('');
    setShowCreateAlert(false);
  };

  // Apply filters and sorting
  let filteredAlerts = [...alerts];
  
  if (typeFilter !== 'All Types') {
    filteredAlerts = filteredAlerts.filter(alert => alert.type === typeFilter);
  }
  
  if (priorityFilter !== 'All Priorities') {
    filteredAlerts = filteredAlerts.filter(alert => alert.priority === priorityFilter);
  }
  
  // Apply sorting
  filteredAlerts.sort((a, b) => {
    if (sortOrder === 'Newest First') {
      return new Date(b.time) - new Date(a.time);
    } else if (sortOrder === 'Oldest First') {
      return new Date(a.time) - new Date(b.time);
    } else if (sortOrder === 'Priority') {
      const priorityOrder = { 'High': 0, 'Medium': 1, 'Low': 2 };
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    }
    return 0;
  });

  return (
    <div>
      <Title>Alerts</Title>
      <Text>Manage and monitor your alerts</Text>

      {/* Filters */}
      <Card className="mt-6">
        <Grid numItemsMd={3} className="gap-4">
          <Col>
            <Text>Filter by Type</Text>
            <Select
              value={typeFilter}
              onValueChange={setTypeFilter}
              className="mt-2"
            >
              <SelectItem value="All Types">All Types</SelectItem>
              {alertTypes.map(type => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </Select>
          </Col>
          <Col>
            <Text>Filter by Priority</Text>
            <Select
              value={priorityFilter}
              onValueChange={setPriorityFilter}
              className="mt-2"
            >
              <SelectItem value="All Priorities">All Priorities</SelectItem>
              {priorities.map(priority => (
                <SelectItem key={priority} value={priority}>
                  {priority}
                </SelectItem>
              ))}
            </Select>
          </Col>
          <Col>
            <Text>Sort by</Text>
            <Select
              value={sortOrder}
              onValueChange={setSortOrder}
              className="mt-2"
            >
              <SelectItem value="Newest First">Newest First</SelectItem>
              <SelectItem value="Oldest First">Oldest First</SelectItem>
              <SelectItem value="Priority">Priority</SelectItem>
            </Select>
          </Col>
        </Grid>
      </Card>

      {/* Create New Alert */}
      <Card className="mt-6">
        <Flex justifyContent="between" alignItems="center">
          <Title>Create New Alert</Title>
          <Button 
            onClick={() => setShowCreateAlert(!showCreateAlert)}
            size="xs"
          >
            {showCreateAlert ? 'Cancel' : 'Create Alert'}
          </Button>
        </Flex>

        {showCreateAlert && (
          <div className="mt-4">
            <Grid numItemsMd={2} className="gap-4">
              <Col>
                <Text>Alert Type</Text>
                <Select
                  value={alertType}
                  onValueChange={setAlertType}
                  className="mt-2"
                >
                  {alertTypes.map(type => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </Select>

                <Text className="mt-4">Condition</Text>
                <TextInput
                  placeholder="Enter alert condition..."
                  value={alertCondition}
                  onChange={(e) => setAlertCondition(e.target.value)}
                  className="mt-2"
                />
              </Col>
              <Col>
                <Text>Priority</Text>
                <Select
                  value={alertPriority}
                  onValueChange={setAlertPriority}
                  className="mt-2"
                >
                  {priorities.map(priority => (
                    <SelectItem key={priority} value={priority}>
                      {priority}
                    </SelectItem>
                  ))}
                </Select>

                <Text className="mt-4">Notification Channels</Text>
                <MultiSelect
                  value={notificationChannels}
                  onValueChange={setNotificationChannels}
                  className="mt-2"
                >
                  {notificationOptions.map(option => (
                    <MultiSelectItem key={option} value={option}>
                      {option}
                    </MultiSelectItem>
                  ))}
                </MultiSelect>
              </Col>
            </Grid>
            <Button onClick={handleCreateAlert} className="mt-4">
              Create Alert
            </Button>
          </div>
        )}
      </Card>

      {/* Alert List */}
      <div className="mt-6 space-y-4">
        {filteredAlerts.length === 0 ? (
          <Card>
            <Text>No alerts found</Text>
          </Card>
        ) : (
          filteredAlerts.map(alert => (
            <AlertCard key={alert.id} alert={alert} />
          ))
        )}
      </div>
    </div>
  );
};

export default Alerts;
