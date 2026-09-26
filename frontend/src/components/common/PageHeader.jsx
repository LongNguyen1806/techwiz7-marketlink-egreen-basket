import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/PageHeader.css';
export function PageHeader({ title, description, actions, className }) {
    return (<div className={cn('page-header', className)}>
      <div>
        <h1 className="page-header__title">{title}</h1>
        {description ? <p className="page-header__description">{description}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </div>);
}

PageHeader.propTypes = {
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    actions: PropTypes.node,
    className: PropTypes.string,
};

