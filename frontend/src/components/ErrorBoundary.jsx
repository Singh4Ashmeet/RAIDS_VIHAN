import { Component } from 'react'

import ErrorState from './ui/ErrorState'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          message={this.state.error.message || 'The interface could not render.'}
          onRetry={() => this.setState({ error: null })}
        />
      )
    }

    return this.props.children
  }
}
