import { ReactNode, useState } from 'react';
import { 
  AppShell, 
  Navbar, 
  Header, 
  Text, 
  MediaQuery, 
  Burger, 
  useMantineTheme,
  Stack,
  NavLink
} from '@mantine/core';
import { 
  IconWallet, 
  IconBell, 
  IconRobot, 
  IconChartBar,
  IconDashboard,
  IconSettings
} from '@tabler/icons-react';
import { useRouter } from 'next/router';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const theme = useMantineTheme();
  const [opened, setOpened] = useState(false);
  const router = useRouter();

  const navItems = [
    { icon: IconDashboard, label: 'Dashboard', path: '/' },
    { icon: IconWallet, label: 'Wallets', path: '/wallets' },
    { icon: IconBell, label: 'Alerts', path: '/alerts' },
    { icon: IconRobot, label: 'Agents', path: '/agents' },
    { icon: IconChartBar, label: 'Analytics', path: '/analytics' },
    { icon: IconSettings, label: 'Settings', path: '/settings' },
  ];

  return (
    <AppShell
      styles={{
        main: {
          background: theme.colorScheme === 'dark' ? theme.colors.dark[8] : theme.colors.gray[0],
        },
      }}
      navbarOffsetBreakpoint="sm"
      navbar={
        <Navbar p="md" hiddenBreakpoint="sm" hidden={!opened} width={{ sm: 200, lg: 250 }}>
          <Navbar.Section>
            <Text size="xl" weight={700} color="blue">Ekko Dashboard</Text>
          </Navbar.Section>
          <Navbar.Section grow mt="lg">
            <Stack spacing={0}>
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  label={item.label}
                  icon={<item.icon size={20} />}
                  active={router.pathname === item.path}
                  onClick={() => {
                    router.push(item.path);
                    setOpened(false);
                  }}
                  style={{ marginBottom: 4 }}
                />
              ))}
            </Stack>
          </Navbar.Section>
        </Navbar>
      }
      header={
        <Header height={70} p="md">
          <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <MediaQuery largerThan="sm" styles={{ display: 'none' }}>
              <Burger
                opened={opened}
                onClick={() => setOpened((o) => !o)}
                size="sm"
                color={theme.colors.gray[6]}
                mr="xl"
              />
            </MediaQuery>
            <Text size="lg" weight={600}>Ekko Blockchain Monitor</Text>
          </div>
        </Header>
      }
    >
      {children}
    </AppShell>
  );
}
