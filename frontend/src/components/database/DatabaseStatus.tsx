/**
 * Database status for the backend PostgreSQL deployment.
 */

import { Server } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export function DatabaseStatus() {
  return (
    <Badge variant="default" className="gap-1.5">
      <Server className="h-3 w-3" />
      后端数据库
    </Badge>
  );
}

export function DatabaseStatusDetail() {
  return (
    <div className="flex items-start gap-3 rounded-lg border p-4">
      <div className="rounded-full bg-muted p-2">
        <Server className="h-5 w-5" />
      </div>
      <div className="flex-1 space-y-1">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-semibold">后端数据库模式</h4>
          <Badge variant="default" className="text-xs">
            API
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          数据存储在后端 PostgreSQL 数据库中，通过 REST API 访问，支持多用户和多设备同步。
        </p>
        <p className="text-xs text-muted-foreground italic">
          所有数据操作均通过后端 API 进行，请确保后端服务和数据库连接正常。
        </p>
      </div>
    </div>
  );
}
