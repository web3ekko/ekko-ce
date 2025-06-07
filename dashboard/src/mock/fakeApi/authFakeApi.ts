import { Server, Response } from 'miragejs';

export default function authFakeApi(server: Server, apiPrefix: string) {
  console.log('Setting up auth routes with prefix:', apiPrefix);

  // Handle the /token endpoint that AuthService calls
  server.post(`/token`, (schema, { requestBody }) => {
    console.log('Mock API /token called with requestBody:', requestBody);
    console.log('Available users in DB:', schema.db.signInUserData);

    // Parse form data (application/x-www-form-urlencoded)
    const params = new URLSearchParams(requestBody);
    const email = params.get('username');
    const password = params.get('password');

    console.log('Parsed credentials:', { email, password });

    const user = schema.db.signInUserData.findBy({
      email,
      password,
    });
    console.log('Found user:', user);

    if (user) {
      console.log('Login successful, returning user:', user);
      return user;
    }
    console.log('Login failed - user not found');
    return new Response(401, { some: 'header' }, { message: 'Invalid email or password!' });
  });

  // Keep the old endpoint for backward compatibility
  server.post(`/users/sign-in`, (schema, { requestBody }) => {
    const { email, password } = JSON.parse(requestBody);
    const user = schema.db.signInUserData.findBy({
      email,
      password,
    });
    console.log('user', user);
    if (user) {
      return user;
    }
    return new Response(401, { some: 'header' }, { message: 'Invalid email or password!' });
  });

  server.post(`${apiPrefix}/sign-out`, () => {
    return true;
  });
}
