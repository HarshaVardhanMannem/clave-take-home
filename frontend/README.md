# Restaurant Analytics Dashboard - Frontend

Next.js frontend for the Restaurant Analytics Agent API. Provides a natural language interface to query restaurant data with dynamic visualizations.

## Features

- 🎯 **Natural Language Queries** - Type questions in plain English
- 📊 **Dynamic Visualizations** - Automatically generates appropriate charts (bar, line, pie, tables)
- 📦 **Widget-Based Dashboard** - Add multiple queries as widgets
- 🔄 **Real-time Query Processing** - Fast API integration
- 💡 **Example Queries** - Quick-start suggestions
- 🎨 **Modern UI** - Clean, responsive design with Tailwind CSS

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Charts**: Chart.js + react-chartjs-2
- **HTTP Client**: Axios
- **Icons**: Lucide React

## Getting Started

### Prerequisites

- Node.js 20+ and npm/yarn
- Backend API running on `http://localhost:8000` (see `restaurant-analytics-agent` directory)

### Installation

```bash
# Install dependencies
npm install

# Copy environment example
cp .env.local.example .env.local

# Edit .env.local if backend runs on different port
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Development

```bash
# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
# Build the application
npm run build

# Start production server
npm start
```

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Main dashboard page
│   └── globals.css         # Global styles
├── components/
│   ├── QueryInput.tsx      # Query input component
│   ├── ChartWidget.tsx     # Chart/widget display
│   ├── ClarificationDialog.tsx  # Clarification UI
│   └── ErrorAlert.tsx      # Error display
├── lib/
│   └── api.ts              # API client
├── types/
│   └── api.ts              # TypeScript types
└── package.json
```

## Usage

1. **Start the backend API** (in `restaurant-analytics-agent` directory):
   ```bash
   python run.py
   ```

2. **Start the frontend**:
   ```bash
   npm run dev
   ```

3. **Ask questions** like:
   - "Show me sales comparison between Downtown and Airport locations"
   - "What were my top 5 selling products last week?"
   - "Compare delivery vs dine-in revenue"
   - "Graph hourly sales for Friday vs Saturday"

4. **View results** as interactive charts and tables

5. **Add more widgets** by asking additional questions

## Environment Variables

- `NEXT_PUBLIC_API_URL` - Backend API URL (default: `http://localhost:8000`)

## Features in Detail

### Query Input
- Text area for natural language queries
- Keyboard shortcut: Enter to submit
- Example query suggestions
- Loading state during processing

### Chart Widgets
- Supports multiple chart types (bar, line, pie, table)
- Shows query, explanation, and metadata
- Copy SQL query
- Remove widgets
- Responsive layout

### Error Handling
- Network errors
- API errors with suggestions
- Clarification requests with suggestions

## Deployment

### Vercel (Recommended)

1. Push code to GitHub
2. Import project in Vercel
3. Set environment variable `NEXT_PUBLIC_API_URL` to your backend URL
4. Deploy

### Other Platforms

Build the application and deploy the `.next` folder:

```bash
npm run build
```

The output will be in the `.next` directory.

## Notes

- Make sure the backend API is running and accessible from the frontend
- The backend should have CORS enabled (already configured)
- Data is from January 1-4, 2025 only (as per backend configuration)
- Next.js 15 requires Node.js 20+

## Troubleshooting

If you encounter import errors:
1. Delete `node_modules` and `package-lock.json`
2. Run `npm install` again
3. Clear Next.js cache: `rm -rf .next` (or `rmdir /s .next` on Windows)
