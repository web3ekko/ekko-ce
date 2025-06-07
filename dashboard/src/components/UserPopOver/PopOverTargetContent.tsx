import { Avatar, Text } from '@mantine/core';
import classes from './PopOverTargetContent.module.css';
import { useAppSelector } from '@/store';

export default function PopOverTargetContent() {
  const { fullName, email } = useAppSelector((state) => state.auth.user || {}); // Ensure user object exists

  const displayName = fullName || 'User'; // Default display name
  const displayEmail = email || '-'; // Default display email

  let initials = 'U'; // Default initial
  if (fullName) {
    const nameParts = fullName.split(' ');
    const firstNameInitial = nameParts[0] ? nameParts[0][0] : '';
    const lastNameInitial = nameParts.length > 1 && nameParts[1] ? nameParts[1][0] : '';
    initials = (firstNameInitial + lastNameInitial).toUpperCase() || 'U';
    if (initials.length === 1 && nameParts[0] && nameParts[0].length > 1) {
      // If only one name part, use first two letters
      initials = nameParts[0].substring(0, 2).toUpperCase();
    } else if (initials.length === 0) {
      initials = 'U';
    }
  } else if (email) {
    initials = email[0].toUpperCase();
  }

  return (
    <>
      <div className={classes.contentWrapper}>
        <Avatar color={'blue'} radius={'lg'}>
          {initials}
        </Avatar>
        <div>
          <Text style={{ fontWeight: 'bold' }} size="md">
            {displayName}
          </Text>
          <Text size="xs">{displayEmail}</Text>
        </div>
      </div>
    </>
  );
}
