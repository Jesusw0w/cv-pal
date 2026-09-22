# CV Pal — frontend

Angular app. Every screen talks to the backend through one HTTP boundary, which mock
mode intercepts.

```bash
npm install
npm run start:mock     # no backend needed — http://localhost:4200
npm start              # against the backend on :8000
npm run lint && npm run format:check && npm test -- --watch=false && npm run build
```

Full setup and build configurations: [../../docs/development.md](../../docs/development.md)
