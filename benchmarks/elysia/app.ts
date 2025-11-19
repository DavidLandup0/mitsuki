import { Elysia } from 'elysia';

const app = new Elysia()
  .get('/', () => ({ message: 'Hello, World!' }))
  .listen(8000);

console.log(`Elysia server running on port ${app.server?.port}`);
