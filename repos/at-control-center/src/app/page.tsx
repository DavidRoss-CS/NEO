'use client';

import { SystemOverview } from '@/components/dashboard/SystemOverview';
import { ServiceMetrics } from '@/components/dashboard/ServiceMetrics';
import { TradingFlow } from '@/components/dashboard/TradingFlow';
import { RealtimeAlerts } from '@/components/dashboard/RealtimeAlerts';

export default function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold leading-7 text-gray-900 dark:text-white sm:truncate sm:text-3xl sm:tracking-tight">
          NEO Control Center
        </h1>
        <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
          Real-time monitoring and control for the NEO Trading Intelligence System v1.0.0
        </p>
      </div>

      {/* System overview cards */}
      <SystemOverview />

      {/* Real-time alerts */}
      <RealtimeAlerts />

      {/* Service metrics */}
      <ServiceMetrics />

      {/* Trading flow visualization */}
      <TradingFlow />
    </div>
  );
}