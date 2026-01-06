'use client';

import { ErrorResponse } from '@/types/api';
import { AlertCircle, X } from 'lucide-react';

interface ErrorAlertProps {
  error: ErrorResponse;
  onClose: () => void;
}

export default function ErrorAlert({ error, onClose }: ErrorAlertProps) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1">
          <AlertCircle className="text-red-500 flex-shrink-0 mt-0.5" size={20} />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-red-900 mb-1">
              {error.error_message}
            </h4>
            {error.details?.error && (
              <p className="text-sm text-red-700 mb-2">{error.details.error}</p>
            )}
            {error.suggestions.length > 0 && (
              <ul className="list-disc list-inside text-sm text-red-700 space-y-1">
                {error.suggestions.map((suggestion, idx) => (
                  <li key={idx}>{suggestion}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-red-400 hover:text-red-600 transition-colors ml-4"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
}




