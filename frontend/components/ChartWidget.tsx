'use client';

import { useMemo, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Bar, Line, Pie, Doughnut } from 'react-chartjs-2';
import { QueryResponse, VisualizationType } from '@/types/api';
import { 
  X, Copy, Check, ChevronDown, ChevronUp, Download, 
  Table, BarChart3, Database, Lightbulb, Clock
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import MetricCard from './MetricCard';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface ChartWidgetProps {
  widget: { id: string; query: string; response: QueryResponse };
  onRemove?: (id: string) => void;
}

// Helper to detect if result is a single metric
function isSingleMetric(results: Record<string, any>[], columns: string[]): boolean {
  if (results.length !== 1) return false;
  // Single row with 1-3 numeric columns is likely a metric
  const numericColumns = columns.filter(col => typeof results[0][col] === 'number');
  return numericColumns.length >= 1 && numericColumns.length <= 3;
}

// Helper to format values intelligently
function formatValue(value: any, columnName: string): string {
  if (value === null || value === undefined) return '-';
  
  if (typeof value === 'number') {
    // Detect currency columns
    const currencyKeywords = ['revenue', 'sales', 'total', 'amount', 'price', 'cost', 'avg_', 'sum_'];
    const isCurrency = currencyKeywords.some(kw => columnName.toLowerCase().includes(kw));
    
    if (isCurrency) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
      }).format(value);
    }
    
    // Detect percentage columns
    if (columnName.toLowerCase().includes('percent') || columnName.toLowerCase().includes('rate')) {
      return `${value.toFixed(1)}%`;
    }
    
    // Regular number
    return new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 2,
    }).format(value);
  }
  
  return String(value);
}

// Helper to determine metric icon
function getMetricIcon(columnName: string): 'dollar' | 'orders' | 'users' | 'store' | 'time' | 'items' {
  const name = columnName.toLowerCase();
  if (name.includes('revenue') || name.includes('sales') || name.includes('total') || name.includes('amount')) return 'dollar';
  if (name.includes('order') || name.includes('count')) return 'orders';
  if (name.includes('customer') || name.includes('user')) return 'users';
  if (name.includes('location') || name.includes('store')) return 'store';
  if (name.includes('time') || name.includes('hour') || name.includes('avg')) return 'time';
  return 'items';
}

export default function ChartWidget({ widget, onRemove }: ChartWidgetProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [showSQL, setShowSQL] = useState(false);
  const { response } = widget;

  const chartData = useMemo(() => {
    if (!response.visualization?.chart_js_config) {
      return null;
    }

    const config = response.visualization.chart_js_config;
    
    if (response.visualization.type === VisualizationType.TABLE) {
      return null;
    }

    return config;
  }, [response.visualization]);

  const handleCopySQL = async () => {
    await navigator.clipboard.writeText(response.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExportCSV = () => {
    if (response.results.length === 0) return;
    
    const headers = response.columns.join(',');
    const rows = response.results.map(row => 
      response.columns.map(col => {
        const val = row[col];
        // Escape commas and quotes in CSV
        if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
          return `"${val.replace(/"/g, '""')}"`;
        }
        return val ?? '';
      }).join(',')
    );
    
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${widget.query.slice(0, 30).replace(/[^a-z0-9]/gi, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderChart = () => {
    if (!chartData) return null;

    const chartType = response.visualization.type;

    switch (chartType) {
      case VisualizationType.BAR_CHART:
      case VisualizationType.STACKED_BAR:
        return <Bar data={chartData.data} options={chartData.options} />;
      
      case VisualizationType.LINE_CHART:
      case VisualizationType.MULTI_SERIES:
        return <Line data={chartData.data} options={chartData.options} />;
      
      case VisualizationType.PIE_CHART:
        return <Pie data={chartData.data} options={chartData.options} />;
      
      default:
        return null;
    }
  };

  const renderMetrics = () => {
    if (!isSingleMetric(response.results, response.columns)) return null;
    
    const row = response.results[0];
    const numericColumns = response.columns.filter(col => typeof row[col] === 'number');
    
    return (
      <div className={`grid gap-4 ${numericColumns.length === 1 ? 'grid-cols-1' : numericColumns.length === 2 ? 'grid-cols-2' : 'grid-cols-3'}`}>
        {numericColumns.map(col => (
          <MetricCard
            key={col}
            title={col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            value={row[col]}
            icon={getMetricIcon(col)}
            format={col.toLowerCase().includes('revenue') || col.toLowerCase().includes('sales') || col.toLowerCase().includes('total') ? 'currency' : 'number'}
            size="lg"
          />
        ))}
      </div>
    );
  };

  const renderTable = () => {
    if (response.results.length === 0) {
      return (
        <div className="text-center py-8 text-gray-500">
          <Database className="mx-auto mb-2 text-gray-400" size={32} />
          <p>No results found</p>
        </div>
      );
    }

    return (
      <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gradient-to-r from-gray-50 to-gray-100 border-b-2 border-gray-200">
            <tr>
              {response.columns.map((col) => (
                <th
                  key={col}
                  className="px-5 py-3.5 text-left text-xs font-bold text-gray-700 uppercase tracking-wider"
                >
                  {col.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {response.results.slice(0, 20).map((row, idx) => (
              <tr key={idx} className="hover:bg-gradient-to-r hover:from-primary-50/50 hover:to-transparent transition-all duration-150">
                {response.columns.map((col) => (
                  <td key={col} className="px-5 py-3.5 whitespace-nowrap text-sm text-gray-800 font-medium">
                    {formatValue(row[col], col)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {response.results.length > 20 && (
          <div className="px-5 py-3.5 bg-gradient-to-r from-gray-50 to-gray-100 text-sm text-gray-600 font-medium border-t-2 border-gray-200">
            Showing 20 of {response.result_count} results
          </div>
        )}
      </div>
    );
  };

  const renderKeyInsights = () => {
    const insights = (response as any).key_insights;
    if (!insights || insights.length === 0) return null;

    return (
      <div className="mt-6 p-5 bg-gradient-to-br from-warning-50 via-amber-50 to-warning-50 rounded-xl border border-warning-200 shadow-sm">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="p-1.5 bg-warning-500 rounded-lg">
            <Lightbulb className="text-white" size={16} />
          </div>
          <span className="text-sm font-bold text-warning-800">Key Insights</span>
        </div>
        <ul className="space-y-2">
          {insights.map((insight: string, idx: number) => (
            <li key={idx} className="text-sm text-warning-900 flex items-start gap-2.5 font-medium">
              <span className="text-warning-500 font-bold mt-0.5">•</span>
              {insight}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-2xl shadow-soft border border-gray-100 overflow-hidden hover:shadow-medium hover-lift transition-all duration-300">
      {/* Header */}
      <div className="px-6 py-5 bg-gradient-to-br from-primary-50 via-primary-50/80 to-white border-b border-primary-100/50">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 mb-2 truncate" title={widget.query}>
              {response.visualization.config.title || widget.query}
            </h3>
            {response.answer && (
              <div className="text-sm text-gray-700 prose prose-sm max-w-none prose-strong:text-primary-700 prose-strong:font-semibold prose-p:my-1">
                <ReactMarkdown>{response.answer}</ReactMarkdown>
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 ml-4 flex-shrink-0">
            <button
              onClick={() => setShowSQL(!showSQL)}
              className={`p-2.5 rounded-xl transition-all duration-200 ${
                showSQL 
                  ? 'bg-primary-500 text-white shadow-md scale-105' 
                  : 'text-gray-500 hover:text-primary-600 hover:bg-primary-50 hover:scale-105'
              }`}
              title="Show SQL"
            >
              <Database size={16} />
            </button>
            <button
              onClick={handleCopySQL}
              className="p-2.5 text-gray-500 hover:text-success-600 hover:bg-success-50 rounded-xl transition-all duration-200 hover:scale-105"
              title="Copy SQL"
            >
              {copied ? <Check size={16} className="text-success-600" /> : <Copy size={16} />}
            </button>
            <button
              onClick={handleExportCSV}
              className="p-2.5 text-gray-500 hover:text-primary-600 hover:bg-primary-50 rounded-xl transition-all duration-200 hover:scale-105 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
              title="Export CSV"
              disabled={response.results.length === 0}
            >
              <Download size={16} />
            </button>
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-2.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-xl transition-all duration-200 hover:scale-105"
              title={expanded ? 'Collapse' : 'Expand'}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {onRemove && (
              <button
                onClick={() => onRemove(widget.id)}
                className="p-2.5 text-gray-500 hover:text-accent-600 hover:bg-accent-50 rounded-xl transition-all duration-200 hover:scale-105"
                title="Remove widget"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>
        
        {/* Meta info badges */}
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-full font-medium shadow-sm hover:shadow-md transition-shadow">
            <BarChart3 size={12} />
            {response.intent.replace(/_/g, ' ')}
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-gray-700 font-medium shadow-sm hover:bg-gray-100 transition-colors">
            <Table size={12} />
            {response.result_count} results
          </span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-gray-700 font-medium shadow-sm hover:bg-gray-100 transition-colors">
            <Clock size={12} />
            {(response.execution_time_ms / 1000).toFixed(2)}s
          </span>
        </div>
      </div>

      {/* SQL Panel (collapsible) */}
      {showSQL && (
        <div className="px-6 py-4 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 border-b border-gray-700">
          <pre className="text-xs text-gray-200 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">
            <code className="text-primary-300">{response.sql}</code>
          </pre>
        </div>
      )}

      {/* Content */}
      {expanded && (
        <div className="p-6">
          {/* Check if single metric first */}
          {isSingleMetric(response.results, response.columns) ? (
            renderMetrics()
          ) : response.visualization.type === VisualizationType.TABLE ? (
            renderTable()
          ) : chartData && response.results.length > 0 ? (
            <>
              {/* Show chart when available */}
              <div className="h-80 mb-6">
                {renderChart()}
              </div>
              {/* Always show table below chart when results exist */}
              <div className="mt-6">
                <div className="mb-3 flex items-center gap-2">
                  <Table size={16} className="text-gray-600" />
                  <h4 className="text-sm font-semibold text-gray-700">Data Table</h4>
                </div>
                {renderTable()}
              </div>
            </>
          ) : response.results.length > 0 ? (
            renderTable()
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Database className="mx-auto mb-2 text-gray-400" size={32} />
              <p>No results found</p>
            </div>
          )}

          {/* Key Insights */}
          {renderKeyInsights()}
        </div>
      )}
    </div>
  );
}

