# Frontend (Next.js)

## Run locally

```bash
cd frontend
npm install
# or: pnpm i / yarn
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000" > .env.local
npm run dev
```

Open `http://localhost:3000`.

Pages:
- `/` landing with typing animation
- `/gen` generation chooser
- `/groups?gen=4th%20Gen` radial group selector
- `/group?name=Stray%20Kids` group details, timeline, prediction


