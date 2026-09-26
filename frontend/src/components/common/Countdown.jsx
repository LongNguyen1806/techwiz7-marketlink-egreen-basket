import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/Countdown.css';
function formatRemaining(ms) {
    if (ms <= 0)
        return 'Expired';
    const totalSec = Math.floor(ms / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h > 48) {
        const days = Math.floor(h / 24);
        return `${days}d ${h % 24}h left`;
    }
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')} left`;
}
export function Countdown({ targetIso, label, className, }) {
    const [text, setText] = useState(() => formatRemaining(new Date(targetIso).getTime() - Date.now()));
    useEffect(() => {
        const tick = () => {
            setText(formatRemaining(new Date(targetIso).getTime() - Date.now()));
        };
        tick();
        const id = window.setInterval(tick, 1000);
        return () => window.clearInterval(id);
    }, [targetIso]);
    return (<p className={cn('countdown', className)}>
      <span className="countdown__label">{label}: </span>
      <span className="countdown__value">{text}</span>
    </p>);
}

Countdown.propTypes = {
    targetIso: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    className: PropTypes.string,
};

