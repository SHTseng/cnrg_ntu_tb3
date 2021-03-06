#include <ros/ros.h>
#include <nav_msgs/Odometry.h>
#include <geometry_msgs/Pose.h>
#include <geometry_msgs/Twist.h>
#include <spencer_tracking_msgs/TrackedPersons.h>

#include <boost/thread.hpp>
#include <memory>

namespace turtlebot_guide
{

enum FollowerState
{
  FOLLOWING,
  NOT_FOLLOWING,
  STOPPED,
  UNKNOWN
};

class FollowerStateMonitor
{

public:

  FollowerStateMonitor():
    wait_for_wake_(true)
  {
    ros::NodeHandle private_nh("~");

    std::vector<double> following_range;
    private_nh.param("following_range", following_range, std::vector<double>());

    for(std::size_t i = 0; i < following_range.size(); i+=2)
    {
      geometry_msgs::Point p;
      p.x = following_range[i];
      p.y = following_range[i+1];
      following_polygon_.push_back(p);
    }

    monitor_thread_ = new boost::thread(boost::bind(&FollowerStateMonitor::monitorThread, this));

    odom_sub_ = nh_.subscribe("odom", 10, &FollowerStateMonitor::odomCB, this);

    track_sub_ = nh_.subscribe("spencer/perception/tracked_persons", 10, &FollowerStateMonitor::trackCB, this);
  }

  ~FollowerStateMonitor()
  {
    monitor_thread_->interrupt();
    monitor_thread_->join();

    delete monitor_thread_;
  }

private:

  void odomCB(const nav_msgs::Odometry::ConstPtr _msg)
  {
    boost::recursive_mutex::scoped_lock lock(monitor_mutex_);
    odom_ = *_msg;
  }

  void trackCB(const spencer_tracking_msgs::TrackedPersons::ConstPtr _msg)
  {
    boost::recursive_mutex::scoped_lock lock(monitor_mutex_);
    tracked_people_ = *_msg;

    wait_for_wake_ = false;
    monitor_cond_.notify_one();
  }

  void monitorThread()
  {
    ros::NodeHandle n;
    while(n.ok())
    {
      boost::unique_lock<boost::recursive_mutex> lock(monitor_mutex_);
      while(wait_for_wake_)
      {
        monitor_cond_.wait(lock);
      }

      FollowerState follower_state;
      if (tracked_people_.tracks.empty())
      {
        follower_state = UNKNOWN;
      }
      else
      {
        // Currently get the only track out
        follower_pose_ = tracked_people_.tracks.front().pose.pose;
        follower_vel_ = tracked_people_.tracks.front().twist.twist;

        // Check the follower is following or not
        follower_state = checkFollowerState();
      }

      // Record the follower pose for next run and unlock the mutex
      prev_follower_pose_ = follower_pose_;
      wait_for_wake_ = true;

      switch(follower_state)
      {
        case FOLLOWING:
        {
          ROS_INFO("Follwoing");
          break;
        }
        case NOT_FOLLOWING:
        {
          ROS_INFO("Not follwoing");
          break;
        }
        case STOPPED:
        {
          ROS_INFO("Stopped");
          break;
        }
        case UNKNOWN:
        {
          ROS_INFO("Unknown");
          break;
        }
      } // end switch

    } // end while
  }

  FollowerState checkFollowerState()
  {
    // Check the follower is moving
    double d = distance(follower_pose_, prev_follower_pose_);
    if(d < 0.001) return STOPPED;

    // Coordinate transformation of the following range
    geometry_msgs::Point transformed_pose = transformToLocalFrame(follower_pose_.position);
    return insidePolygon(following_polygon_, transformed_pose) ? FOLLOWING : NOT_FOLLOWING;
  }

  bool insidePolygon(const std::vector<geometry_msgs::Point> &polygon, const geometry_msgs::Point &p)
  {
    // Calculate each segment of polyong counter clockwise and check the point lies in the left side of the line
    bool left_side = true;
    double area;
    for (std::size_t i = 0; i < polygon.size()-1; i++)
    {
      // outer product to calculate area surrounded by point and two adjent vertices
      area = (polygon[i].x-p.x)*(polygon[i+1].y-p.y)-(polygon[i+1].x-p.x)*(polygon[i].y-p.y);
      // if the value with different sign indicates the point lies in the right side
      if(area < 0.0) left_side = false;
    }

    // Calculate the last point and first point
    area = (polygon.back().x-p.x)*(polygon.front().y-p.y)-(polygon.front().x-p.x)*(polygon.back().y-p.y);
    if(area < 0.0) left_side = false;

    return left_side;
  }

  geometry_msgs::Point transformToLocalFrame(const geometry_msgs::Point &p)
  {
    geometry_msgs::Point transformed_p;
    // hacks to transform the frame to odom, TODO: use tf
    transformed_p.x = p.x - odom_.pose.pose.position.x;
    transformed_p.y = p.y - odom_.pose.pose.position.y;
    return transformed_p;
  }

  double distance(const geometry_msgs::Pose &p1, const geometry_msgs::Pose &p2)
  {
    return hypot(p1.position.x-p2.position.x, p1.position.y-p2.position.y);
  }

  ros::NodeHandle nh_;

  ros::Subscriber odom_sub_;
  ros::Subscriber track_sub_;

  nav_msgs::Odometry odom_;
  spencer_tracking_msgs::TrackedPersons tracked_people_;

  geometry_msgs::Pose follower_pose_;
  geometry_msgs::Pose prev_follower_pose_;
  geometry_msgs::Twist follower_vel_;

  std::vector<geometry_msgs::Point> following_polygon_;
  std::vector<geometry_msgs::Point> camera_polygon_;

  boost::thread *monitor_thread_;
  boost::recursive_mutex monitor_mutex_;
  boost::condition_variable_any monitor_cond_;

  bool wait_for_wake_;

};


} // end namespace

typedef std::shared_ptr<turtlebot_guide::FollowerStateMonitor> FollowerStateMonitorPtr;

int main (int argc, char *argv[])
{
  ros::init(argc, argv, "follower_state_monitor");
  FollowerStateMonitorPtr monitor(new turtlebot_guide::FollowerStateMonitor());

  ros::spin();
  return 0;
}
