import { RestartScope } from '../utils/settings';

interface RestartBadgeProps {
  scope: RestartScope;
}

export function RestartBadge({ scope }: RestartBadgeProps) {
  if (scope === 'none') {
    return null;
  }

  const getBadgeConfig = (scope: RestartScope) => {
    switch (scope) {
      case 'backend':
        return {
          text: 'Restart Required',
          className: 'restart-badge restart-badge--backend'
        };
      case 'app':
        return {
          text: 'App Restart Required',
          className: 'restart-badge restart-badge--app'
        };
      case 'full':
        return {
          text: 'Full Restart Required',
          className: 'restart-badge restart-badge--full'
        };
      default:
        return null;
    }
  };

  const config = getBadgeConfig(scope);
  if (!config) return null;

  return (
    <span className={config.className} title={`This setting requires a ${scope} restart to take effect`}>
      {config.text}
    </span>
  );
}