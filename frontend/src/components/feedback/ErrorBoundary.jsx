import { Component } from 'react';
import PropTypes from 'prop-types';
import { Button } from '../ui/Button';
import '../../styles/common/ErrorBoundary.css';
/** Catches render errors in the React tree and shows a recovery UI. */
export class ErrorBoundary extends Component {
    state = { hasError: false };
    static getDerivedStateFromError() {
        return { hasError: true };
    }
    componentDidCatch(error, info) {
        console.error('Unhandled UI error', error, info.componentStack);
    }
    handleRetry = () => {
        this.setState({ hasError: false });
    };
    render() {
        if (this.state.hasError) {
            return (<div className="error-boundary">
          <h1 className="error-boundary__title">Something went wrong</h1>
          <p className="error-boundary__message">
            This screen hit an unexpected error. Try again, or refresh the page.
          </p>
          <Button type="button" onClick={this.handleRetry}>
            Try again
          </Button>
        </div>);
        }
        return this.props.children;
    }
}

ErrorBoundary.propTypes = {
    children: PropTypes.node,
};

