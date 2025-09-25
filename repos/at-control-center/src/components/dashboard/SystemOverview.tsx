'use client';

import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ArrowTrendingUpIcon,
  ClockIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline';
import { useSystemMetrics } from '@/hooks/useSystemMetrics';
import { MetricCard } from '@/components/ui/MetricCard';
import { StatusIndicator } from '@/components/ui/StatusIndicator';

export function SystemOverview() {
  const { data: metrics, isLoading } = useSystemMetrics();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg animate-pulse">
            <div className="p-5">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2"></div>
              <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  const systemHealth = metrics?.systemHealth || 'unknown';
  const getHealthColor = () => {
    switch (systemHealth) {
      case 'healthy': return 'green';
      case 'warning': return 'yellow';
      case 'critical': return 'red';
      default: return 'gray';
    }
  };

  const getHealthIcon = () => {
    switch (systemHealth) {
      case 'healthy': return CheckCircleIcon;
      case 'warning': return ExclamationTriangleIcon;
      case 'critical': return XCircleIcon;
      default: return ClockIcon;
    }
  };

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {/* System Health */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <MetricCard
          title="System Health"
          value={systemHealth}
          icon={getHealthIcon()}
          color={getHealthColor()}
          subtitle={`${metrics?.servicesUp || 0}/${metrics?.totalServices || 0} services online`}
        />
      </motion.div>

      {/* Request Rate */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <MetricCard
          title="Request Rate"
          value={`${metrics?.requestRate || 0}/sec`}
          icon={ArrowTrendingUpIcon}
          color="blue"
          subtitle="Webhooks processed"
          change={metrics?.requestRateChange}
        />
      </motion.div>

      {/* End-to-End Latency */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <MetricCard
          title="E2E Latency"
          value={`${metrics?.e2eLatency || 0}ms`}
          icon={ClockIcon}
          color={metrics?.e2eLatency > 900 ? 'red' : metrics?.e2eLatency > 500 ? 'yellow' : 'green'}
          subtitle="P95 webhook to delivery"
        />
      </motion.div>

      {/* Success Rate */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <MetricCard
          title="Success Rate"
          value={`${((metrics?.successRate || 0) * 100).toFixed(1)}%`}
          icon={CheckCircleIcon}
          color={metrics?.successRate < 0.95 ? 'red' : metrics?.successRate < 0.99 ? 'yellow' : 'green'}
          subtitle="Overall system reliability"
        />
      </motion.div>

      {/* Active Agents */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <MetricCard
          title="Active Agents"
          value={metrics?.activeAgents || 0}
          icon={ArrowTrendingUpIcon}
          color="purple"
          subtitle="AI agents processing"
        />
      </motion.div>

      {/* Paper Trading Balance */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <MetricCard
          title="Trading Balance"
          value={`$${(metrics?.tradingBalance || 0).toLocaleString()}`}
          icon={CurrencyDollarIcon}
          color="green"
          subtitle="Paper trading portfolio"
        />
      </motion.div>

      {/* Messages in Queue */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7 }}
      >
        <MetricCard
          title="Message Queue"
          value={metrics?.queueDepth || 0}
          icon={ClockIcon}
          color={metrics?.queueDepth > 1000 ? 'red' : metrics?.queueDepth > 100 ? 'yellow' : 'green'}
          subtitle="NATS pending messages"
        />
      </motion.div>

      {/* Feature Flags */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
      >
        <div className="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <CheckCircleIcon className="h-6 w-6 text-gray-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                    Feature Flags
                  </dt>
                  <dd className="flex items-baseline">
                    <div className="text-2xl font-semibold text-gray-900 dark:text-white">
                      {metrics?.featureFlagsEnabled || 0}/{metrics?.totalFeatureFlags || 0}
                    </div>
                    <div className="ml-2 text-sm text-gray-600 dark:text-gray-300">
                      enabled
                    </div>
                  </dd>
                </dl>
              </div>
            </div>
            <div className="mt-3 flex space-x-1">
              {metrics?.featureFlags?.map((flag: any) => (
                <StatusIndicator
                  key={flag.name}
                  status={flag.enabled ? 'online' : 'offline'}
                  size="sm"
                  tooltip={`${flag.name}: ${flag.enabled ? 'enabled' : 'disabled'}`}
                />
              ))}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}