import { createServer } from 'miragejs';
import { signInUserData } from './data/authData';
import authFakeApi from '@/mock/fakeApi/authFakeApi';
import appConfig from '@/configs/app.config';

const { apiPrefix } = appConfig;

export function mockServer() {
  console.log('Initializing mock server with apiPrefix:', apiPrefix);

  return createServer({
    seeds(server) {
      server.db.loadData({
        signInUserData,
      });
      console.log('Mock server seeded with data:', signInUserData);
    },
    routes() {
      this.urlPrefix = apiPrefix;
      this.namespace = '';

      // Log all requests
      this.pretender.handledRequest = function(verb, path, request) {
        console.log(`Mock server handled: ${verb} ${path}`);
      };

      this.pretender.unhandledRequest = function(verb, path) {
        console.log(`Mock server unhandled: ${verb} ${path}`);
      };

      authFakeApi(this, '');

      // Passthrough for external resources
      this.passthrough((request) => {
        const isExternal = request.url.startsWith('http') && !request.url.includes('localhost');
        const isResource = request.url.startsWith('data:text');
        return isExternal || isResource;
      });
    },
  });
}
